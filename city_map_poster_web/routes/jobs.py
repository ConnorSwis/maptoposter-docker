import threading
from flask import Blueprint, Response, current_app, jsonify, request

from ..jobs import JobStore, run_generate_job


bp = Blueprint("jobs", __name__)


def _parse_coord(value, label: str):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {label}.") from exc


@bp.post("/generate")
def generate():
    data = request.json or {}
    city = data.get("city")
    country = data.get("country")
    theme = data.get("theme")
    radius = str(data.get("radius", 15000))
    features: list[str] = data.get("features", [])
    try:
        lat = _parse_coord(data.get("lat"), "latitude")
        lon = _parse_coord(data.get("lon"), "longitude")
        star_lat = _parse_coord(data.get("star_lat"), "star latitude")
        star_lon = _parse_coord(data.get("star_lon"), "star longitude")
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    if not city or not country:
        return jsonify({"success": False, "error": "City and Country required."}), 400

    if (lat is None) ^ (lon is None):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Latitude and longitude must be provided together.",
                }
            ),
            400,
        )
    if (star_lat is None) ^ (star_lon is None):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Star latitude and longitude must be provided together.",
                }
            ),
            400,
        )

    config = current_app.extensions["config"]
    logger = current_app.extensions["logger"]
    store: JobStore = current_app.extensions["job_store"]

    cmd = [
        "python",
        "create_map_poster.py",
        "--city",
        city,
        "--country",
        country,
        "--distance",
        radius,
        "--theme",
        theme,
    ]
    if lat is not None and lon is not None:
        cmd.extend(["--lat", str(lat), "--lon", str(lon)])
    if star_lat is not None and star_lon is not None:
        cmd.extend(["--star-lat", str(star_lat), "--star-lon", str(star_lon)])
    if features:
        cmd.extend(["--enable-features", ",".join(features)])

    job = store.create()

    t = threading.Thread(
        target=run_generate_job,
        args=(config, job, cmd, logger),
        daemon=True,
        name=f"job-{job.id}",
    )
    t.start()

    return jsonify({"success": True, "job_id": job.id})


@bp.get("/jobs/<job_id>")
def job_status(job_id: str):
    store: JobStore = current_app.extensions["job_store"]
    job = store.get(job_id)
    if not job:
        return jsonify({"success": False, "error": "Unknown job_id"}), 404

    return jsonify(
        {
            "success": True,
            "job_id": job.id,
            "done": job.done,
            "ok": job.ok,
            "filename": job.filename,
            "error": job.error,
            "stage_id": job.stage_id,
            "stage_label": job.stage_label,
        }
    )


@bp.get("/jobs/<job_id>/logs")
def job_logs(job_id: str):
    store: JobStore = current_app.extensions["job_store"]
    job = store.get(job_id)
    if not job:
        return jsonify({"success": False, "error": "Unknown job_id"}), 404

    def gen():
        yield ": connected\n\n"
        while True:
            chunk = job.q.get()
            if chunk == "":
                break
            yield chunk

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return Response(gen(), headers=headers)
