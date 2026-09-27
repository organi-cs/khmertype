from khmertyper.chart import ERR, NET, RAW, render_chart


def test_chart_shape_and_labels():
    lines = render_chart([10, 20, 30, 40], [12, 25, 28, 45], [0, 1, 0, 0], width=40, height=6)
    assert len(lines) == 6 + 3  # plot rows, axis, errors, time labels
    assert len({len(line) for line in lines}) == 1  # rectangular
    assert lines[0].lstrip().startswith("50")       # nice max above 45
    assert lines[5].lstrip().startswith("0 |")
    assert "+" in lines[6] and set(lines[6].strip()) <= {"+", "-"}
    assert lines[-1].strip().startswith("1s") and lines[-1].strip().endswith("4s")


def test_chart_uses_only_ascii():
    lines = render_chart([5.0] * 30, [6.0] * 30, [0] * 30)
    assert all(ch.isascii() for line in lines for ch in line)


def test_error_marks_line_up_with_seconds():
    lines = render_chart([10, 10, 10], [10, 10, 10], [1, 0, 1], width=3, height=4)
    marks = lines[-2]
    assert marks.count(ERR) == 2


def test_net_drawn_over_raw_and_higher_values_higher():
    lines = render_chart([10, 90], [10, 20], [0, 0], width=2, height=10)
    rows_with_net = [i for i, line in enumerate(lines) if NET in line]
    assert len(rows_with_net) == 2
    col_of = [line.index("|") for line in lines[:10]]
    # second point is higher (smaller row index) than the first
    first_row = next(i for i, line in enumerate(lines[:10]) if line[col_of[i] + 1] == NET)
    second_row = next(i for i, line in enumerate(lines[:10]) if line[col_of[i] + 2] == NET)
    assert second_row < first_row
    assert not any(line[col_of[i] + 1] == RAW for i, line in enumerate(lines[:10]))  # hidden under net


def test_long_series_is_bucketed_to_width():
    lines = render_chart(list(range(120)), list(range(120)), [0] * 120, width=30, height=5)
    plot = lines[0].split("|", 1)[1]
    assert len(plot) == 30


def test_empty_series():
    assert render_chart([], [], []) == ["(no data)"]
