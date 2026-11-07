"""Publication TikTok séparée de la génération vidéo.

Les credentials sont lus depuis un fichier local non suivi, une variable base64
ou le secret TIKTOK_SESSIONID. Rien n'est écrit dans le dépôt et les secrets ne
sont jamais affichés dans les logs.
"""
from __future__ import annotations

import argparse
import base64
import os
import tempfile
from datetime import datetime
from pathlib import Path


def _cookies_from_env_or_file(cookies_file: Path | None) -> tuple[str | None, list[dict] | None, Path | None]:
    """Retourne (cookies_path, cookies_list, temporary_path_to_cleanup)."""
    if cookies_file is not None:
        if not cookies_file.exists():
            raise FileNotFoundError(f"Fichier cookies introuvable : {cookies_file}")
        return str(cookies_file), None, None

    encoded = os.getenv("TIKTOK_COOKIES_B64", "").strip()
    if encoded:
        try:
            content = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ValueError("TIKTOK_COOKIES_B64 n'est pas un base64 valide") from exc
        handle = tempfile.NamedTemporaryFile(prefix="reelforge_tiktok_", suffix=".cookies", delete=False)
        handle.write(content)
        handle.close()
        path = Path(handle.name)
        return str(path), None, path

    sessionid = os.getenv("TIKTOK_SESSIONID", "").strip()
    if sessionid:
        return None, [{
            "name": "sessionid",
            "value": sessionid,
            "domain": ".tiktok.com",
            "path": "/",
            "expiry": 2147483647,
        }], None
    raise ValueError(
        "Authentification absente : utilisez --cookies-file, TIKTOK_COOKIES_B64 "
        "ou le secret TIKTOK_SESSIONID"
    )


def publish_video(video: Path, description: str, cookies_file: Path | None = None,
                  schedule: str | None = None, cover: Path | None = None,
                  comment: bool = True, stitch: bool = True, duet: bool = True,
                  product_id: str | None = None) -> None:
    if not video.exists():
        raise FileNotFoundError(f"Vidéo introuvable : {video}")
    if cover is not None and not cover.exists():
        raise FileNotFoundError(f"Cover introuvable : {cover}")

    try:
        from tiktok_uploader.upload import TikTokUploader
    except ImportError as exc:
        raise RuntimeError(
            "Dépendance absente. Installez tiktok-uploader puis lancez `playwright install`."
        ) from exc

    cookies_path, cookies_list, temporary_path = _cookies_from_env_or_file(cookies_file)
    try:
        kwargs = {"cookies": cookies_path} if cookies_path else {"cookies_list": cookies_list}
        uploader = TikTokUploader(**kwargs)
        upload_kwargs = {
            "description": description,
            "comment": comment,
            "stitch": stitch,
            "duet": duet,
        }
        if schedule:
            upload_kwargs["schedule"] = datetime.fromisoformat(schedule)
        if cover:
            upload_kwargs["cover"] = str(cover)
        if product_id:
            upload_kwargs["product_id"] = product_id
        uploader.upload_video(str(video), **upload_kwargs)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publie un MP4 sur TikTok")
    parser.add_argument("--video", required=True, help="MP4 local ou artifact téléchargé")
    parser.add_argument("--description", default="", help="Description et hashtags TikTok")
    parser.add_argument("--cookies-file", default=None, help="cookies.txt local, jamais commité")
    parser.add_argument("--schedule", default=None, help="Date ISO UTC, au moins 20 min dans le futur")
    parser.add_argument("--cover", default=None)
    parser.add_argument("--product-id", default=None)
    parser.add_argument("--no-comment", action="store_true")
    parser.add_argument("--no-stitch", action="store_true")
    parser.add_argument("--no-duet", action="store_true")
    args = parser.parse_args()
    publish_video(
        Path(args.video), args.description,
        cookies_file=Path(args.cookies_file) if args.cookies_file else None,
        schedule=args.schedule, cover=Path(args.cover) if args.cover else None,
        comment=not args.no_comment, stitch=not args.no_stitch, duet=not args.no_duet,
        product_id=args.product_id,
    )
    print(f"Publication demandée pour {args.video}")


if __name__ == "__main__":
    main()
