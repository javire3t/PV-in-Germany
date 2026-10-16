from PIL import Image

from figures.germany.animation import gif_frame


def test_gif_transparency_survives_animation_disposal(tmp_path):
    palette = Image.new('P', (1, 1))
    palette.putpalette([0, 0, 0, 0, 180, 90] + [255, 255, 255] * 253 + [0, 0, 0])
    frames = []
    for position in (1, 2):
        image = Image.new('RGBA', (4, 4), (255, 255, 255, 0))
        image.putpixel((position, 1), (0, 180, 90, 255))
        image.putpixel((0, 3), (0, 0, 0, 255))
        frames.append(gif_frame(image, palette))
    path = tmp_path / 'animation.gif'
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=1000,
                   transparency=255, background=255, disposal=2, optimize=False)
    with Image.open(path) as gif:
        assert gif.n_frames == 2
        assert 'loop' not in gif.info
        for index, position in enumerate((1, 2)):
            gif.seek(index)
            rgba = gif.convert('RGBA')
            assert rgba.getpixel((0, 0))[3] == 0
            assert rgba.getpixel((position, 1)) == (0, 180, 90, 255)
            assert rgba.getpixel((0, 3)) == (0, 0, 0, 255)
            assert rgba.getpixel((3 - position, 1))[3] == 0
