# Stash WebP Screenshot Remover Plugin

A Stash plugin that automatically removes `.webp` scene screenshots (cover images) and replaces them with `.jpg` versions.

## Features

- **Automatic Detection**: Scans all scenes in your Stash library for WebP screenshots
- **Smart Conversion**: Only converts WebP images to JPG (skips already-converted images)
- **Format Detection**: Checks image format by magic bytes and PIL to ensure accuracy
- **Detailed Reporting**: Provides statistics on processed scenes and conversions
- **Error Handling**: Gracefully handles missing files and API errors

## Installation

1. Clone or download this plugin to your Stash plugins directory:
   ```
   ~/.stash (Linux)
   ~/AppData/Roaming/Stash (Windows)
   ```

2. Restart Stash or refresh the plugins

## Configuration

The plugin uses environment variables that Stash automatically provides:

- `STASH_URL`: The Stash server URL (default: `http://localhost:9999`)
- `STASH_API_KEY`: API key for authentication (if required)

## Usage

### Via Stash UI

1. Navigate to **Settings → Plugins**
2. Find **WebP Screenshot Remover**
3. Click **Execute** to run the plugin

### Via Command Line

```bash
python webp_remover.py
```

## How It Works

1. Connects to your Stash instance via GraphQL API
2. Scans the Stash blobs directory for WebP files
3. Retrieves all scenes and their screenshot URLs
4. For each scene, downloads the screenshot and checks if it's WebP format
5. Converts WebP images to JPG with 90% quality
6. Uploads the JPG back to Stash as the new cover image
7. Generates a report with conversion statistics

## Output

The plugin returns a JSON response with:

```json
{
  "success": true,
  "stats": {
    "total_scenes": 351,
    "webp_screenshots_found": 5,
    "successfully_replaced": 5,
    "replacements": [
      {
        "scene_id": "9",
        "title": "Scene Title",
        "original_url": "http://localhost:9999/scene/9/screenshot?t=1768234519",
        "action": "converted_webp_to_jpg"
      }
    ],
    "errors": []
  }
}
```
```

## Requirements

- Python 3.6+
- `requests` library (usually included with Stash)
- Pillow 9.0.0+
- Stash 0.10.0+

## Troubleshooting

### "Connection refused" Error

Make sure Stash is running and accessible at the URL specified in `STASH_URL`.

### "No WebP files found" Message

The plugin scans for WebP files before processing. If this message appears, there are no WebP files to convert in your Stash blobs directory.

### API Authentication Issues

If your Stash instance requires authentication, ensure the `STASH_API_KEY` environment variable is properly set.

## Notes

- Only WebP images are converted; JPG and PNG screenshots are skipped automatically
- Conversion quality is set to 90% to maintain good image quality while reducing file size
- Converted JPG images replace the original WebP in Stash metadata
- The original WebP files in the blobs directory are not deleted
- Always backup your Stash database before running plugins

## License

MIT License
