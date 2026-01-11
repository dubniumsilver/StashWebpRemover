import os
from datetime import datetime
from PIL import Image
from stashapi.stashapp import StashInterface, StashPlugin

class StashWebpRemover(StashPlugin):

    def run(self):
        stash = StashInterface(conn=self.conn)

        # Load settings
        dry_run = self.get_setting("dry_run")
        delete_webp = self.get_setting("delete_webp")
        jpg_quality = int(self.get_setting("jpg_quality"))
        convert_only_missing = self.get_setting("convert_only_missing")
        rebuild_paths = self.get_setting("rebuild_paths")
        skip_multi = self.get_setting("skip_multi_image")
        batch_limit = int(self.get_setting("batch_limit"))
        write_report = self.get_setting("write_report")
        preview_mode = self.get_setting("preview_mode")

        self.error("Starting WebP → JPG conversion...")
        self.error(f"Dry run: {dry_run}")
        self.error(f"Delete original .webp: {delete_webp}")
        self.error(f"JPG quality: {jpg_quality}")
        self.error(f"Convert only missing JPGs: {convert_only_missing}")
        self.error(f"Rebuild screenshot paths: {rebuild_paths}")
        self.error(f"Skip multi-image scenes: {skip_multi}")
        self.error(f"Batch limit: {batch_limit if batch_limit > 0 else 'No limit'}")
        self.error(f"Write report: {write_report}")
        self.error(f"Preview mode: {preview_mode}")

        scenes = stash.find_scenes({})
        total = len(scenes)
        processed = 0
        converted = 0
        report_lines = []

        for i, scene in enumerate(scenes, start=1):
            if batch_limit > 0 and processed >= batch_limit:
                break

            self.progress(i / total)
            self.error(f"[{i}/{total}] Scene {scene['id']}")

            screenshot = scene.get("paths", {}).get("screenshot")
            if not screenshot:
                continue

            # Skip scenes with multiple images
            if skip_multi and len(scene.get("paths", {}).get("images", [])) > 1:
                continue

            # Determine paths
            is_webp = screenshot.lower().endswith(".webp")
            jpg_path = screenshot[:-5] + ".jpg"

            # Convert only missing JPGs
            if convert_only_missing and os.path.exists(jpg_path):
                continue

            # PREVIEW MODE: only list what WOULD be converted
            if preview_mode:
                if is_webp and (not convert_only_missing or not os.path.exists(jpg_path)):
                    msg = f"[PREVIEW] Would convert: {screenshot} → {jpg_path}"
                    self.error(msg)
                    report_lines.append(msg)
                    processed += 1
                continue


            # Rebuild paths only
            if rebuild_paths and not is_webp:
                if not dry_run:
                    stash.update_scene({
                        "id": scene["id"],
                        "paths": {"screenshot": screenshot}
                    })
                processed += 1
                continue

            # Only convert .webp files
            if not is_webp:
                continue

            try:
                if not dry_run:
                    img = Image.open(screenshot).convert("RGB")
                    img.save(jpg_path, "JPEG", quality=jpg_quality)

                    stash.update_scene({
                        "id": scene["id"],
                        "paths": {"screenshot": jpg_path}
                    })

                    if delete_webp:
                        os.remove(screenshot)

                converted += 1
                processed += 1
                msg = f"Converted: {screenshot} → {jpg_path}"
                self.error(msg)
                report_lines.append(msg)

            except Exception as e:
                err = f"Error converting {screenshot}: {e}"
                self.error(err)
                report_lines.append(err)

        self.error(f"Done. Processed {processed} scenes. Converted {converted}.")

        # Write report
        if write_report:
            try:
                report_path = os.path.join(
                    os.path.dirname(__file__),
                    f"conversion_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                )
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(report_lines))
                self.error(f"Report written to: {report_path}")
            except Exception as e:
                self.error(f"Failed to write report: {e}")

def main():
    StashWebpRemover().run()

if __name__ == "__main__":
    main()