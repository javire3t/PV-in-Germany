"""Crop exported artwork to its pixels; GIFs use one box for every frame."""

# Allow running this file directly from an editor or any working directory.
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from io import BytesIO
from pathlib import Path
import argparse
import json

from PIL import Image, ImageChops, ImageOps
import numpy as np


def save_image_atomic(image, target, **kwargs):
    """Write an image completely before replacing an existing output file."""
    target = Path(target)
    temporary = target.with_name(target.name + '.tmp')
    image.save(temporary, format='PNG', **kwargs)
    temporary.replace(target)


def content_box(image):
    rgba = image.convert('RGBA')
    alpha = rgba.getchannel('A')
    if alpha.getextrema()[0] < 255:
        return alpha.getbbox()
    # Older exports have an opaque white canvas.
    difference = ImageChops.difference(rgba.convert('RGB'), Image.new('RGB', rgba.size, 'white'))
    return difference.getbbox() or (0, 0, *rgba.size)


def union_box(boxes):
    boxes = [box for box in boxes if box is not None]
    if not boxes:
        raise ValueError('Cannot crop an empty figure')
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def safety_margin(box):
    return max(8, round(min(box[2]-box[0], box[3]-box[1]) * .012))


def padded_crop(image, box, margin):
    rgba = image.convert('RGBA')
    fill = (255, 255, 255, 0) if rgba.getchannel('A').getextrema()[0] < 255 else (255, 255, 255, 255)
    return ImageOps.expand(rgba.crop(box), border=margin, fill=fill)


def already_padded(box, size, margin):
    return box == (margin, margin, size[0]-margin, size[1]-margin)


def save_cropped(fig, target, **kwargs):
    """Render all artists before removing even the remaining transparent margin."""
    kwargs.update(transparent=True, bbox_inches='tight', pad_inches=.08)
    validate_caption_layout(fig)
    buffer = BytesIO()
    fig.savefig(buffer, format='png', **kwargs)
    buffer.seek(0)
    with Image.open(buffer) as image:
        box = union_box([content_box(image)])
        cropped = padded_crop(image, box, safety_margin(box))
        save_image_atomic(cropped, target, dpi=image.info.get('dpi', (fig.dpi, fig.dpi)))


def save_animation_frame(fig, target):
    """Fixed frame canvas includes captions below the plotting canvas."""
    from matplotlib.transforms import Bbox
    validate_caption_layout(fig)
    # Render to memory first.  At the larger animation resolution a direct
    # save can leave a partially written PNG if the file is inspected while
    # the encoder is still flushing; the GIF builder must only see complete
    # frames.
    buffer = BytesIO()
    fig.savefig(buffer, format='png', transparent=True,
                bbox_inches=Bbox.from_extents(0, -3, fig.get_figwidth(), fig.get_figheight()))
    payload = buffer.getvalue()
    with Image.open(BytesIO(payload)) as check:
        check.load()
    Path(target).write_bytes(payload)


def validate_caption_layout(fig):
    captions = [text for text in fig.texts if text.get_gid() == 'figure_caption']
    if not captions:
        return
    renderer = fig.canvas.get_renderer()
    content_bottom = min(ax.get_tightbbox(renderer).y0 for ax in fig.axes)
    credits = [text.get_window_extent(renderer) for text in fig.texts if text.get_gid() == 'source_credit']
    for caption in captions:
        box = caption.get_window_extent(renderer)
        if box.y1 >= content_bottom:
            raise ValueError('Figure caption overlaps the plot or its labels')
        if credits and max(credit.y1 for credit in credits) >= box.y0:
            raise ValueError('Figure caption overlaps source credits')


def crop_file(path, margin=None):
    path = Path(path)
    with Image.open(path) as image:
        original_size = image.size
        info = image.info.copy()
        if image.format != 'GIF':
            box = union_box([content_box(image)])
            padding = safety_margin(box) if margin is None else margin
            if already_padded(box, original_size, padding):
                return None
            cropped = padded_crop(image, box, padding)
            save_options = {'dpi': info['dpi']} if 'dpi' in info else {}
            save_image_atomic(cropped, path, **save_options)
            return {'file': str(path), 'before': original_size, 'after': cropped.size}
        frames, durations, boxes = [], [], []
        for index in range(image.n_frames):
            image.seek(index)
            frame = image.convert('RGBA')
            frames.append(frame)
            durations.append(image.info.get('duration', 100))
            boxes.append(content_box(frame))
    box = union_box(boxes)
    padding = safety_margin(box) if margin is None else margin
    if already_padded(box, original_size, padding):
        return None
    transparent = any(frame.getchannel('A').getextrema()[0] == 0 for frame in frames)
    indexed = []
    for frame in frames:
        cropped = padded_crop(frame, box, padding)
        rgb = cropped.convert('RGB')
        alpha = cropped.getchannel('A')
        visible_box = alpha.getbbox()
        if visible_box:
            # Use an actual opaque pixel even when the bounding-box corner is empty.
            visible_color = rgb.getpixel(next((x, y) for y in range(visible_box[1], visible_box[3])
                                              for x in range(visible_box[0], visible_box[2])
                                              if alpha.getpixel((x, y)) == 255))
        else:
            visible_color = (0, 0, 0)
        rgb.paste(visible_color, mask=alpha.point(lambda value: 255-value))
        counts = rgb.getcolors(256)
        if counts is None or len(counts) > (255 if transparent else 256):
            raise ValueError('GIF palette cannot preserve all visible colors')
        colors = sorted(color for count, color in counts)
        packed_colors = np.array([(r << 16) | (g << 8) | b for r, g, b in colors], dtype=np.uint32)
        pixels = np.asarray(rgb, dtype=np.uint32)
        packed_pixels = (pixels[:, :, 0] << 16) | (pixels[:, :, 1] << 8) | pixels[:, :, 2]
        indices = np.searchsorted(packed_colors, packed_pixels).astype(np.uint8)
        indices[np.asarray(alpha) == 0] = 255
        while len(colors) < 256:
            colors.append(colors[0])
        indexed_frame = Image.fromarray(indices).convert('P')
        indexed_frame.putpalette([channel for color in colors for channel in color])
        if transparent:
            indexed_frame.info['transparency'] = 255
        indexed.append(indexed_frame)
    options = dict(save_all=True, append_images=indexed[1:], duration=durations,
                   disposal=2, optimize=False)
    if transparent:
        options.update(transparency=255, background=255)
    if 'loop' in info:
        options['loop'] = info['loop']
    if 'comment' in info:
        options['comment'] = info['comment']
    buffer = BytesIO()
    indexed[0].save(buffer, format='GIF', **options)
    buffer.seek(0)
    with Image.open(buffer) as check:
        assert check.n_frames == len(frames), 'Cropping changed GIF frame count'
        assert check.info.get('loop') == info.get('loop'), 'Cropping changed GIF playback'
        for index, frame in enumerate(frames):
            check.seek(index)
            expected = padded_crop(frame, box, padding)
            actual = check.convert('RGBA')
            assert check.info.get('duration', 100) == durations[index]
            assert actual.getchannel('A').tobytes() == expected.getchannel('A').tobytes()
            difference = ImageChops.difference(actual.convert('RGB'), expected.convert('RGB'))
            # RGB below transparent pixels is irrelevant; visible pixels must match.
            for channel in difference.split():
                assert ImageChops.multiply(channel, expected.getchannel('A')).getbbox() is None, 'GIF colors changed'
    path.write_bytes(buffer.getvalue())
    return {'file': str(path), 'before': original_size, 'after': indexed[0].size,
            'frames': len(frames)}


def main():
    from project_paths import FINAL_OUTPUTS, INTERMEDIATE_OUTPUTS
    parser = argparse.ArgumentParser(description=__doc__)
    # Cropping rewrites files in place, so only final figures are touched unless asked.
    parser.add_argument('folders', nargs='*', type=Path, default=[FINAL_OUTPUTS])
    args = parser.parse_args()
    results = []
    for folder in args.folders:
        for path in sorted(folder.rglob('*')):
            if path.suffix.lower() in {'.png', '.gif'}:
                result = crop_file(path)
                if result:
                    results.append(result)
                    print(f"{path.name}: {result['before']} -> {result['after']}", flush=True)
    audit = INTERMEDIATE_OUTPUTS / 'crop_validation.json'
    audit.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(f'Cropped {len(results)} figures and GIFs.', flush=True)


if __name__ == '__main__':
    main()
