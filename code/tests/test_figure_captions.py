import matplotlib.pyplot as plt

from figures.shared.source_credits import add_source_footer


def test_caption_and_sources_use_one_compact_shared_block():
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.set_title('Installed photovoltaic capacity in selected federal states')
    ax.set_xlabel('Year')
    ax.plot([2000, 2026], [1, 10])
    credits = add_source_footer(fig, ['Visualization: EIFER', 'Data: Energy-Charts.info'])
    assert ax.get_title() == ''
    caption = next(text for text in fig.texts if text.get_gid() == 'figure_caption')
    assert caption.get_fontweight() == 'bold'
    assert caption.get_color() == '#17372C'
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    assert caption.get_window_extent(renderer).y1 < ax.get_tightbbox(renderer).y0
    assert [text.get_text() for text in credits] == [
        'Installed photovoltaic capacity in selected federal states',
        'Visualization: EIFER',
        'Data: Energy-Charts.info',
    ]
    assert all(text.get_gid() in {'figure_caption', 'source_credit'} for text in credits)
    plt.close(fig)


def test_animation_caption_has_no_year_and_preserves_colorbar_title():
    fig = plt.figure(figsize=(14, 7))
    ax = fig.add_axes([.1, .2, .6, .6])
    colorbar = fig.add_axes([.85, .2, .02, .6])
    colorbar.set_title('kWp/km²')
    add_source_footer(fig, ['Data: Energy-Charts.info'], title='Photovoltaic density by district')
    caption = next(text for text in fig.texts if text.get_gid() == 'figure_caption')
    assert caption.get_text() == 'Photovoltaic density by district'
    assert colorbar.get_title() == 'kWp/km²'
    plt.close(fig)


def test_static_footer_detail_size_is_capped_and_consistent():
    for width, height, dpi in [(10, 5.5, 100), (12, 15.75, 180)]:
        fig = plt.figure(figsize=(width, height), dpi=dpi)
        ax = fig.add_axes([.1, .2, .75, .7])
        credits = add_source_footer(fig, ['Visualization: EIFER'], title='Photovoltaic density')
        assert credits[1].get_fontsize() == 8
        assert credits[2].get_fontsize() == 8
        plt.close(fig)


def test_portrait_footer_is_capped_and_source_lines_do_not_split():
    fig = plt.figure(figsize=(12, 15.75), dpi=100)
    ax = fig.add_axes([.05, .1, .8, .85])
    lines = ['Visualization: EIFER', 'Data: Energy-Charts.info · Last update 17.09.26',
             'Boundaries: © BKG 2026 · VG250, 31 Dec 2025 · dl-de/by-2-0']
    credits = add_source_footer(fig, lines, title='Photovoltaic density by district · 2026')
    # The shared renderer intentionally normalises every figure to one
    # visualization line plus one data line; extra legacy metadata is not
    # allowed to create figure-specific footer heights or wrapped rows.
    assert [text.get_text() for text in credits[1:]] == [
        'Visualization: EIFER',
        'Data: Energy-Charts.info · Last update 17.09.26',
    ]
    assert max(text.get_fontsize() for text in credits) <= 10
    caption = next(text for text in fig.texts if text.get_gid() == 'figure_caption')
    assert '\n' not in caption.get_text()
    assert caption.get_fontsize() <= 23.4 + 1e-8
    plt.close(fig)
