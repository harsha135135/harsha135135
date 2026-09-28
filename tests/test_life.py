"""Tests for the Life engine, the pattern library, the composition and the banner."""

from __future__ import annotations

import random

import pytest

from life import composition as comp
from life.engine import advance, bounding_box, next_generation, period, run, update_ages, window
from life.patterns import (
    BEACON, BEEHIVE, BLINKER, BLOCK, BOAT, CATALOGUE, CLOCK, EATER, GLIDER, GOSPER_GLIDER_GUN,
    KOKS_GALAXY, LOAF, LWSS, MOLD, OCTAGON_2, PENTADECATHLON, POND, PULSAR, TOAD, TUB, Pattern,
    glider_heading,
)
from life.verify import reference_step


def shifted(cells, dx, dy):
    return frozenset((x + dx, y + dy) for x, y in cells)


# --- the four rules -------------------------------------------------------------------


def test_underpopulation_lone_cell_and_pair_die():
    assert next_generation({(0, 0)}) == frozenset()
    assert next_generation({(0, 0), (1, 0)}) == frozenset()


def test_survival_with_two_or_three_neighbours():
    # the middle of a blinker has 2 neighbours; a block cell has 3
    assert (1, 0) in next_generation({(0, 0), (1, 0), (2, 0)})
    assert next_generation(BLOCK.cells) == BLOCK.cells


def test_overpopulation_kills_a_cell_with_four_neighbours():
    plus = {(1, 0), (0, 1), (1, 1), (2, 1), (1, 2)}
    assert (1, 1) not in next_generation(plus)


def test_reproduction_on_exactly_three():
    assert next_generation({(0, 0), (1, 0), (0, 1)}) == BLOCK.cells
    # a dead cell with 2 or 4 neighbours stays dead
    assert (1, 1) not in next_generation({(0, 0), (2, 2)})
    assert (1, 1) not in next_generation({(0, 0), (2, 0), (0, 2), (2, 2)})


def test_empty_world_stays_empty():
    assert next_generation(set()) == frozenset()


@pytest.mark.parametrize("seed", range(8))
def test_engine_matches_independent_reference_on_random_soups(seed):
    rng = random.Random(seed)
    state = frozenset((x, y) for x in range(24) for y in range(24) if rng.random() < 0.35)
    for _ in range(60):
        assert next_generation(state) == frozenset(reference_step(set(state)))
        state = next_generation(state)


# --- canonical patterns -------------------------------------------------------------------


@pytest.mark.parametrize("pattern", [BLOCK, BEEHIVE, LOAF, BOAT, TUB, POND, EATER])
def test_still_lifes_do_not_change(pattern):
    assert next_generation(pattern.cells) == pattern.cells


def test_blinker_flips_and_returns_after_two_generations():
    one = next_generation(BLINKER.cells)
    assert one == frozenset({(1, -1), (1, 0), (1, 1)})      # vertical
    assert next_generation(one) == BLINKER.cells


@pytest.mark.parametrize("pattern, p", [(TOAD, 2), (BEACON, 2), (CLOCK, 2), (PULSAR, 3),
                                        (MOLD, 4), (OCTAGON_2, 5), (KOKS_GALAXY, 8),
                                        (PENTADECATHLON, 15)])
def test_oscillator_periods(pattern, p):
    assert period(pattern.cells, 40) == p


def test_catalogue_periods_are_what_it_claims():
    for name, (pattern, p) in CATALOGUE.items():
        assert period(pattern.cells, 40) == p, name


def test_glider_moves_one_cell_diagonally_every_four_generations():
    assert advance(GLIDER.cells, 4) == shifted(GLIDER.cells, 1, 1)
    assert advance(GLIDER.cells, 40) == shifted(GLIDER.cells, 10, 10)
    for g in range(1, 4):                                   # not before
        assert advance(GLIDER.cells, g) != shifted(GLIDER.cells, 1, 1)


@pytest.mark.parametrize("direction, step", [("se", (1, 1)), ("sw", (-1, 1)),
                                             ("ne", (1, -1)), ("nw", (-1, -1))])
def test_reflected_gliders_fly_the_other_diagonals(direction, step):
    g = glider_heading(direction).cells
    assert advance(g, 4) == shifted(g, *step)


def test_lightweight_spaceship_moves_two_cells_every_four_generations():
    assert advance(LWSS.cells, 4) == shifted(LWSS.cells, -2, 0)


def test_gosper_gun_fires_one_glider_every_30_generations():
    gun = GOSPER_GLIDER_GUN.cells
    assert len(gun) == 36
    core = lambda s: frozenset(c for c in s if c[0] < 36 and c[1] < 9)   # noqa: E731
    later = advance(gun, 30 * 20)
    assert core(later) == core(gun)                          # the gun itself is period 30
    stray = later - core(later)
    # every 30 generations one more glider: 5 cells each, travelling south-east
    assert len(stray) == 5 * 20
    assert core(advance(gun, 30)) == core(gun) and advance(gun, 30) != gun


def test_gun_stream_lanes_match_what_the_composition_assumes():
    gun = GOSPER_GLIDER_GUN.cells
    far = [c for c in advance(gun, 300) if c[1] > 12]
    assert {x - y for x, y in far} == set(range(12, 16))


def test_eater_swallows_a_glider_and_repairs_itself():
    eater = EATER.at(10, 10)
    glider = GLIDER.at(3, 3)
    assert advance(eater | glider, 40) == eater


def test_transforms_are_consistent():
    g = GLIDER
    assert g.rotate(4).cells == g.cells
    assert g.flip_x().flip_x().cells == g.cells
    assert g.flip_y().flip_y().cells == g.cells
    assert g.transpose().transpose().cells == g.cells
    assert g.rotate(2).cells == g.flip_x().flip_y().cells
    assert BLOCK.at(5, 7) == frozenset({(5, 7), (6, 7), (5, 8), (6, 8)})


def test_rle_reader_matches_picture():
    rle = Pattern.from_rle("glider", "x = 3, y = 3\nbo$2bo$3o!")
    assert rle.cells == GLIDER.cells


def test_ages_are_metadata_only():
    ages = {}
    state = GLIDER.cells
    for _ in range(12):
        ages = update_ages(ages, state)
        assert set(ages) == set(state)
        state = next_generation(state)
    assert all(a >= 1 for a in ages.values())


def test_run_yields_every_generation():
    states = list(run(BLINKER.cells, 4))
    assert len(states) == 5 and states[0] == states[2] == states[4]


# --- the composition ------------------------------------------------------------------


@pytest.fixture(scope="module")
def scene():
    return comp.build_scene()


def test_every_part_behaves_like_its_pattern_on_its_own(scene):
    for part in scene.parts:
        if part.period not in (0, 30):
            assert period(part.cells, 30) == part.period, part.name


def test_all_machinery_together_has_a_period_dividing_the_loop(scene):
    fixed = frozenset().union(*(p.cells for p in scene.parts if p.period not in (0, 30)))
    p = period(fixed, comp.LOOP)
    assert p is not None and comp.LOOP % p == 0 and comp.LOOP % 30 == 0


def test_nothing_stands_in_the_meteor_lanes(scene):
    lo, hi = comp.meteor_lanes()
    for part in scene.parts:
        if part.period:
            assert all(not lo - 4 <= x + y <= hi + 4 for x, y in part.cells), part.name


def test_rewind_glider_is_exact():
    g = GLIDER.at(50, 50)
    for t in range(0, 17):
        assert advance(comp.rewind_glider(g, t), t) == g


def test_print_job_recipe_is_an_exact_cycle():
    from life.verify import check_print_job
    check_print_job()


def test_window_repeats_exactly_after_one_loop(scene):
    state = advance(scene.cells, comp.START)
    after = advance(state, comp.LOOP)
    assert window(state, 0, 0, comp.COLS, comp.ROWS) == window(after, 0, 0, comp.COLS, comp.ROWS)


def test_scene_fits_the_window(scene):
    fixed = frozenset().union(*(p.cells for p in scene.parts if p.period))
    x0, y0, x1, y1 = bounding_box(fixed)
    assert x0 >= 0 and y0 >= 0 and x1 < comp.COLS and y1 < comp.ROWS


# --- colour is metadata --------------------------------------------------------------


@pytest.mark.parametrize("theme_name", ["dark", "light"])
def test_theme_never_uses_a_colour_for_both_live_and_dead(theme_name):
    from life.renderer import THEMES
    theme = next(t for t in THEMES if t.name == theme_name)
    assert not theme.live_colours() & theme.dead_colours()
    assert len(theme.colours()) < 255                  # index 255 is GIF transparency


def test_themes_have_the_same_palette_layout():
    from life.renderer import DARK, LIGHT
    assert len(DARK.colours()) == len(LIGHT.colours())


def test_every_visible_cell_has_a_region():
    from life.renderer import ZONES
    zone_of = comp.zone_function()
    seen = {zone_of((x, y)) for x in range(comp.COLS) for y in range(comp.ROWS)}
    assert seen <= set(ZONES) and {"systems", "making", "sky", "flight"} <= seen


def test_orbit_lane_is_empty_apart_from_travellers(scene):
    for part in scene.parts:
        if part.period:
            assert all(y > comp.ORBIT_ROWS for _, y in part.cells), part.name


def test_rack_printer_and_tripod_share_a_baseline(scene):
    bottoms = {p.name: max(y for _, y in p.cells) for p in scene.parts
               if p.name in ("rack", "enclosure", "tripod")}
    assert set(bottoms.values()) == {comp.BASELINE}, bottoms


def test_satellite_survives_every_pass():
    from life.verify import check_satellite
    check_satellite()


# --- the published banner -------------------------------------------------------------


@pytest.fixture(scope="module")
def banner():
    from life.generate import simulate, view, zone_map
    v = view()
    return v, zone_map(v), simulate()


def test_simulated_generations_follow_conway(banner):
    from life.verify import check_rules
    check_rules(banner[2])


def test_trails_are_only_recently_dead_cells(banner):
    frames = banner[2]
    for prev2, prev1, f in zip(frames, frames[1:], frames[2:]):
        for c, k in f.trails.items():
            assert c not in f.state
            assert c in (prev1.state if k == 1 else prev2.state)


@pytest.mark.parametrize("theme_name", ["dark", "light"])
def test_gif_is_an_exact_picture_of_conway(banner, theme_name):
    from PIL import Image

    from life.generate import GIF_NAMES
    from life.renderer import THEMES
    from life.verify import ASSETS, check_gif
    v, _, frames = banner
    theme = next(t for t in THEMES if t.name == theme_name)
    gif = ASSETS / GIF_NAMES[theme_name]
    if not gif.exists():
        pytest.skip("run `python -m life.generate` first")
    with Image.open(gif) as im:
        assert im.size == v.size == (1400, 540)
        assert im.n_frames == comp.LOOP
        assert im.info.get("loop") == 0
    assert gif.stat().st_size < 5_000_000
    check_gif(gif, v, frames, theme)


def test_loop_is_seamless_in_pixels(banner):
    from life.generate import render_frame
    from life.renderer import THEMES
    from life.verify import check_loop
    v, zones, frames = banner
    check_loop(v, zones, frames, render_frame, THEMES)
