"""
阵列与镜像位置计算 — 纯 Python 数学函数。

群星 GUI 没有旋转/镜像属性，所有操作仅改变 position。
"""
from __future__ import annotations

import math
from typing import List, Tuple


PosSizePair = Tuple[Tuple[int, int], Tuple[int, int]]  # ((x, y), (w, h))


def compute_linear_array(
    sources: List[PosSizePair],
    count: int,
    offset_x: int,
    offset_y: int,
) -> List[List[PosSizePair]]:
    """计算线性阵列。

    Parameters
    ----------
    sources : 源控件的 (position, size) 列表
    count : 复制数量（不含原件）
    offset_x, offset_y : 每步偏移量

    Returns
    -------
    List[List[PosSizePair]]
        外层按复制序号（1..count），内层按源控件序号。
        每项为 ((new_x, new_y), (w, h))。
    """
    result = []
    for step in range(1, count + 1):
        copies = []
        for (sx, sy), (w, h) in sources:
            nx = sx + offset_x * step
            ny = sy + offset_y * step
            copies.append(((nx, ny), (w, h)))
        result.append(copies)
    return result


def compute_circular_array(
    sources: List[PosSizePair],
    count: int,
    center_x: float,
    center_y: float,
    radius: float = 0.0,
    mode: str = 'center',
) -> Tuple[List[List[PosSizePair]], List[PosSizePair]]:
    """计算圆形阵列。

    Parameters
    ----------
    sources : 源控件的 (position, size) 列表
    count : 新建副本数量
    center_x, center_y : 圆心坐标
    radius : 固定半径（0 = 自动）
    mode : 'center' — 选中控件为圆心，副本分布在环上
           'on_ring' — 选中控件在环上为起点，副本填充其余位置

    Returns
    -------
    (new_copies, original_moves)
        new_copies: List[List[PosSizePair]] — 每步的新副本
        original_moves: List[PosSizePair] — 原件需要移动到的位置（仅 on_ring 模式有值）
    """
    if count < 1:
        return [], []

    if mode == 'center':
        # 选中控件为圆心：在环上创建 count 个副本
        if radius <= 0:
            radius = 100.0  # 默认半径
        angle_step = 2 * math.pi / count
        result = []
        for step in range(count):
            copies = []
            for (sx, sy), (w, h) in sources:
                a = angle_step * step
                new_cx = center_x + radius * math.cos(a)
                new_cy = center_y + radius * math.sin(a)
                nx = int(round(new_cx - w / 2))
                ny = int(round(new_cy - h / 2))
                copies.append(((nx, ny), (int(w), int(h))))
            result.append(copies)
        return result, []

    else:  # on_ring
        # 选中控件在环上为起点，总共 count+1 个位置（含原件）
        total = count + 1
        angle_step = 2 * math.pi / total

        # 计算原件到圆心的距离和角度
        source_info = []
        for (sx, sy), (w, h) in sources:
            scx = sx + w / 2
            scy = sy + h / 2
            dx = scx - center_x
            dy = scy - center_y
            r = radius if radius > 0 else math.sqrt(dx * dx + dy * dy)
            if r < 1:
                r = 100.0
            a = math.atan2(dy, dx)
            source_info.append((r, a, w, h))

        # 原件移动到 angle 0 位置
        original_moves = []
        for r, a, w, h in source_info:
            new_cx = center_x + r * math.cos(a)
            new_cy = center_y + r * math.sin(a)
            nx = int(round(new_cx - w / 2))
            ny = int(round(new_cy - h / 2))
            original_moves.append(((nx, ny), (int(w), int(h))))

        # 其余 count 个副本
        result = []
        for step in range(1, total):
            copies = []
            for r, a, w, h in source_info:
                new_a = a + angle_step * step
                new_cx = center_x + r * math.cos(new_a)
                new_cy = center_y + r * math.sin(new_a)
                nx = int(round(new_cx - w / 2))
                ny = int(round(new_cy - h / 2))
                copies.append(((nx, ny), (int(w), int(h))))
            result.append(copies)
        return result, original_moves


def compute_mirror(
    sources: List[PosSizePair],
    axis: str,
) -> List[PosSizePair]:
    """计算镜像位置。

    围绕所有源控件的集合中心进行镜像翻转。

    Parameters
    ----------
    sources : 源控件的 (position, size) 列表
    axis : 'h' (水平轴=上下翻转) 或 'v' (垂直轴=左右翻转)

    Returns
    -------
    List[PosSizePair]
        镜像后的 ((new_x, new_y), (w, h)) 列表，顺序与 sources 对应。
    """
    if not sources:
        return []

    # 计算集合包围盒中心
    all_left = min(x for (x, y), (w, h) in sources)
    all_right = max(x + w for (x, y), (w, h) in sources)
    all_top = min(y for (x, y), (w, h) in sources)
    all_bottom = max(y + h for (x, y), (w, h) in sources)
    center_x = (all_left + all_right) / 2
    center_y = (all_top + all_bottom) / 2

    result = []
    for (sx, sy), (w, h) in sources:
        if axis == 'v':
            # 垂直轴镜像（左右翻转）
            scx = sx + w / 2
            new_cx = 2 * center_x - scx
            nx = int(round(new_cx - w / 2))
            result.append(((nx, sy), (w, h)))
        else:
            # 水平轴镜像（上下翻转）
            scy = sy + h / 2
            new_cy = 2 * center_y - scy
            ny = int(round(new_cy - h / 2))
            result.append(((sx, ny), (w, h)))
    return result
