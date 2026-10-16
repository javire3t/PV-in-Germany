from PIL import Image

from figures.shared.crop_exports import crop_file, content_box


def test_png_crop_keeps_opaque_white_artwork_and_removes_transparent_margin(tmp_path):
    path = tmp_path / 'figure.png'
    image = Image.new('RGBA', (20, 15), (255, 255, 255, 0))
    image.paste((255, 255, 255, 255), (4, 3, 12, 10))
    image.save(path)
    crop_file(path, margin=0)
    with Image.open(path) as result:
        assert result.size == (8, 7)
        assert result.getpixel((0, 0)) == (255, 255, 255, 255)
    assert crop_file(path, margin=0) is None


def test_gif_crop_uses_all_frames_and_preserves_local_palettes_and_timing(tmp_path):
    path = tmp_path / 'animation.gif'
    frames = []
    for index, position in enumerate(((3, 4), (15, 12))):
        frame = Image.new('P', (20, 16), 255)
        color = (30 + index, 70, 90)
        frame.putpalette(list(color) + [0, 0, 0] * 255)
        frame.putpixel(position, 0)
        frame.info['transparency'] = 255
        frames.append(frame)
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=[100, 2500], transparency=255, background=255,
                   disposal=2, optimize=False)
    crop_file(path, margin=0)
    with Image.open(path) as result:
        assert result.size == (13, 9)
        assert result.n_frames == 2
        assert 'loop' not in result.info
        for index, point in enumerate(((0, 0), (12, 8))):
            result.seek(index)
            assert result.info['duration'] == [100, 2500][index]
            assert result.convert('RGBA').getpixel(point) == (30 + index, 70, 90, 255)
    assert crop_file(path, margin=0) is None


def test_default_margin_protects_artwork_without_accumulating(tmp_path):
    path = tmp_path / 'padded.png'
    image = Image.new('RGBA', (20, 20), (255, 255, 255, 0))
    image.putpixel((5, 5), (0, 0, 0, 255))
    image.putpixel((14, 14), (0, 0, 0, 255))
    image.save(path)
    crop_file(path)
    with Image.open(path) as result:
        assert result.size == (26, 26)
        assert result.getpixel((8, 8)) == (0, 0, 0, 255)
        assert result.getpixel((0, 0))[3] == 0
    assert crop_file(path) is None


def test_opaque_canvas_removes_only_outer_white_space():
    image = Image.new('RGB', (20, 15), 'white')
    image.putpixel((5, 6), (0, 0, 0))
    image.putpixel((14, 12), (10, 40, 60))
    assert content_box(image) == (5, 6, 15, 13)
