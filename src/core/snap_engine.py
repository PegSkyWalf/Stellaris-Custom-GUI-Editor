"""
智能吸附引擎 — 在拖拽时提供对齐吸附和等距检测。

算法概要：
  - 维护六个有序数组（左/右/上/下边缘、水平中心、垂直中心）
  - 使用 bisect 二分搜索以 O(log n) 找到最近候选
  - 支持边缘对齐、中心对齐、等间距检测三种吸附模式
  - 纯 Python 实现，不依赖 PySide6
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class SnapLine:
    """一条吸附参考线。"""
    position: float          # 参考线坐标（水平线为 y 值，垂直线为 x 值）
    is_horizontal: bool      # True = 水平线, False = 垂直线
    start: float             # 参考线可视起点（正交方向坐标）
    end: float               # 参考线可视终点
    label: str = ''          # 可选标注（如间距值）


@dataclass
class SnapResult:
    """吸附查询结果。"""
    dx: float = 0.0          # X 方向修正量（加到拖拽位置上）
    dy: float = 0.0          # Y 方向修正量
    snapped_x: bool = False  # 是否在 X 方向发生了吸附
    snapped_y: bool = False  # 是否在 Y 方向发生了吸附
    guides: List[SnapLine] = field(default_factory=list)


# 内部使用的矩形定义
RectTuple = Tuple[float, float, float, float]  # (x, y, width, height)


class SnapEngine:
    """智能吸附引擎。

    使用方式：
        1. 拖拽开始时调用 rebuild_index()，传入所有非拖拽物体的矩形
        2. 拖拽过程中每帧调用 query_snap()，传入当前拖拽矩形
        3. 将返回的 dx/dy 加到拖拽位置上实现吸附
    """

    def __init__(self, threshold: float = 5.0):
        self._threshold = threshold
        # 有序数组：(坐标值, 物体id)
        self._lefts: List[Tuple[float, int]] = []
        self._rights: List[Tuple[float, int]] = []
        self._tops: List[Tuple[float, int]] = []
        self._bottoms: List[Tuple[float, int]] = []
        self._cx: List[Tuple[float, int]] = []  # 水平中心
        self._cy: List[Tuple[float, int]] = []  # 垂直中心
        # 原始矩形索引
        self._rects: Dict[int, RectTuple] = {}

    @property
    def threshold(self) -> float:
        return self._threshold

    @threshold.setter
    def threshold(self, v: float):
        self._threshold = max(1.0, min(50.0, v))

    def rebuild_index(self, rects: List[Tuple[int, RectTuple]]) -> None:
        """重建吸附索引。

        Parameters
        ----------
        rects : list of (id, (x, y, w, h))
            所有可吸附物体的 ID 和矩形。
        """
        self._rects.clear()
        lefts, rights, tops, bottoms, cxs, cys = [], [], [], [], [], []

        for obj_id, (x, y, w, h) in rects:
            self._rects[obj_id] = (x, y, w, h)
            lefts.append((x, obj_id))
            rights.append((x + w, obj_id))
            tops.append((y, obj_id))
            bottoms.append((y + h, obj_id))
            cxs.append((x + w / 2, obj_id))
            cys.append((y + h / 2, obj_id))

        self._lefts = sorted(lefts)
        self._rights = sorted(rights)
        self._tops = sorted(tops)
        self._bottoms = sorted(bottoms)
        self._cx = sorted(cxs)
        self._cy = sorted(cys)

    def query_snap(self, rect: RectTuple,
                   snap_edges: bool = True,
                   snap_centers: bool = True,
                   snap_spacing: bool = True) -> SnapResult:
        """查询吸附。

        Parameters
        ----------
        rect : (x, y, w, h)
            当前拖拽物体的矩形。
        snap_edges : bool
            是否检测边缘对齐。
        snap_centers : bool
            是否检测中心对齐。
        snap_spacing : bool
            是否检测等间距。

        Returns
        -------
        SnapResult
            包含修正量和参考线信息。
        """
        x, y, w, h = rect
        r = x + w
        b = y + h
        cx = x + w / 2
        cy = y + h / 2
        t = self._threshold

        best_dx: Optional[float] = None
        best_dy: Optional[float] = None
        guides: List[SnapLine] = []

        # -- 边缘对齐 --
        if snap_edges:
            # X 方向：left-to-left, left-to-right, right-to-left, right-to-right
            for drag_edge, arrays in [
                (x, [self._lefts, self._rights]),
                (r, [self._lefts, self._rights]),
            ]:
                for arr in arrays:
                    match = self._find_nearest(arr, drag_edge, t)
                    if match is not None:
                        delta = match - drag_edge
                        if best_dx is None or abs(delta) < abs(best_dx):
                            best_dx = delta

            # Y 方向：top-to-top, top-to-bottom, bottom-to-top, bottom-to-bottom
            for drag_edge, arrays in [
                (y, [self._tops, self._bottoms]),
                (b, [self._tops, self._bottoms]),
            ]:
                for arr in arrays:
                    match = self._find_nearest(arr, drag_edge, t)
                    if match is not None:
                        delta = match - drag_edge
                        if best_dy is None or abs(delta) < abs(best_dy):
                            best_dy = delta

        # -- 中心对齐 --
        if snap_centers:
            match_cx = self._find_nearest(self._cx, cx, t)
            if match_cx is not None:
                delta = match_cx - cx
                if best_dx is None or abs(delta) < abs(best_dx):
                    best_dx = delta

            match_cy = self._find_nearest(self._cy, cy, t)
            if match_cy is not None:
                delta = match_cy - cy
                if best_dy is None or abs(delta) < abs(best_dy):
                    best_dy = delta

        # -- 等间距检测 --
        if snap_spacing and self._rects:
            sp_dx, sp_dy, sp_guides = self._check_spacing(x, y, w, h, t)
            if sp_dx is not None:
                if best_dx is None or abs(sp_dx) < abs(best_dx):
                    best_dx = sp_dx
            if sp_dy is not None:
                if best_dy is None or abs(sp_dy) < abs(best_dy):
                    best_dy = sp_dy
            guides.extend(sp_guides)

        dx = best_dx if best_dx is not None else 0.0
        dy = best_dy if best_dy is not None else 0.0

        # 生成对齐参考线
        if abs(dx) > 0 or abs(dy) > 0 or snap_edges or snap_centers:
            guides.extend(self._build_guides(x + dx, y + dy, w, h,
                                             snap_edges, snap_centers))

        return SnapResult(
            dx=dx, dy=dy,
            snapped_x=best_dx is not None,
            snapped_y=best_dy is not None,
            guides=guides,
        )

    def _find_nearest(self, arr: List[Tuple[float, int]],
                      value: float, threshold: float) -> Optional[float]:
        """在有序数组中二分查找最近值，阈值内返回坐标。"""
        if not arr:
            return None
        keys = [a[0] for a in arr]
        idx = bisect.bisect_left(keys, value)
        best = None
        best_dist = threshold + 1

        for i in (idx - 1, idx):
            if 0 <= i < len(arr):
                dist = abs(arr[i][0] - value)
                if dist <= threshold and dist < best_dist:
                    best = arr[i][0]
                    best_dist = dist

        return best

    def _check_spacing(self, x: float, y: float, w: float, h: float,
                       threshold: float
                       ) -> Tuple[Optional[float], Optional[float], List[SnapLine]]:
        """检测等间距吸附。

        找到拖拽物体两侧最近的邻居，检查间距是否可以匹配。
        """
        guides: List[SnapLine] = []
        sp_dx: Optional[float] = None
        sp_dy: Optional[float] = None

        if len(self._rects) < 2:
            return sp_dx, sp_dy, guides

        r = x + w
        b = y + h

        # X 方向：找左侧和右侧最近的物体
        left_neighbor = self._find_neighbor_left(x, y, b)
        right_neighbor = self._find_neighbor_right(r, y, b)

        if left_neighbor is not None and right_neighbor is not None:
            ln_id, ln_rect = left_neighbor
            rn_id, rn_rect = right_neighbor
            gap_left = x - (ln_rect[0] + ln_rect[2])   # 拖拽左边 - 左邻右边
            gap_right = rn_rect[0] - r                  # 右邻左边 - 拖拽右边
            desired = (gap_left + gap_right) / 2
            delta = desired - gap_left
            if abs(delta) <= threshold:
                sp_dx = delta

        # Y 方向：找上方和下方最近的物体
        top_neighbor = self._find_neighbor_top(y, x, r)
        bottom_neighbor = self._find_neighbor_bottom(b, x, r)

        if top_neighbor is not None and bottom_neighbor is not None:
            tn_id, tn_rect = top_neighbor
            bn_id, bn_rect = bottom_neighbor
            gap_top = y - (tn_rect[1] + tn_rect[3])
            gap_bottom = bn_rect[1] - b
            desired = (gap_top + gap_bottom) / 2
            delta = desired - gap_top
            if abs(delta) <= threshold:
                sp_dy = delta

        return sp_dx, sp_dy, guides

    def _find_neighbor_left(self, x: float, y1: float, y2: float
                            ) -> Optional[Tuple[int, RectTuple]]:
        """找 X 方向左侧且垂直范围重叠的最近物体。"""
        best = None
        best_dist = float('inf')
        for obj_id, (ox, oy, ow, oh) in self._rects.items():
            obj_right = ox + ow
            if obj_right <= x:
                # 垂直重叠检测
                if oy + oh > y1 and oy < y2:
                    dist = x - obj_right
                    if dist < best_dist:
                        best = (obj_id, (ox, oy, ow, oh))
                        best_dist = dist
        return best

    def _find_neighbor_right(self, r: float, y1: float, y2: float
                             ) -> Optional[Tuple[int, RectTuple]]:
        """找 X 方向右侧且垂直范围重叠的最近物体。"""
        best = None
        best_dist = float('inf')
        for obj_id, (ox, oy, ow, oh) in self._rects.items():
            if ox >= r:
                if oy + oh > y1 and oy < y2:
                    dist = ox - r
                    if dist < best_dist:
                        best = (obj_id, (ox, oy, ow, oh))
                        best_dist = dist
        return best

    def _find_neighbor_top(self, y: float, x1: float, x2: float
                           ) -> Optional[Tuple[int, RectTuple]]:
        """找 Y 方向上方且水平范围重叠的最近物体。"""
        best = None
        best_dist = float('inf')
        for obj_id, (ox, oy, ow, oh) in self._rects.items():
            obj_bottom = oy + oh
            if obj_bottom <= y:
                if ox + ow > x1 and ox < x2:
                    dist = y - obj_bottom
                    if dist < best_dist:
                        best = (obj_id, (ox, oy, ow, oh))
                        best_dist = dist
        return best

    def _find_neighbor_bottom(self, b: float, x1: float, x2: float
                              ) -> Optional[Tuple[int, RectTuple]]:
        """找 Y 方向下方且水平范围重叠的最近物体。"""
        best = None
        best_dist = float('inf')
        for obj_id, (ox, oy, ow, oh) in self._rects.items():
            if oy >= b:
                if ox + ow > x1 and ox < x2:
                    dist = oy - b
                    if dist < best_dist:
                        best = (obj_id, (ox, oy, ow, oh))
                        best_dist = dist
        return best

    def _build_guides(self, x: float, y: float, w: float, h: float,
                      snap_edges: bool, snap_centers: bool) -> List[SnapLine]:
        """为当前吸附位置生成参考线。"""
        guides: List[SnapLine] = []
        r = x + w
        b = y + h
        cx = x + w / 2
        cy = y + h / 2
        t = 0.5  # 精确匹配阈值

        # 扫描所有物体，找到对齐的参考线
        for obj_id, (ox, oy, ow, oh) in self._rects.items():
            obj_r = ox + ow
            obj_b = oy + oh
            obj_cx = ox + ow / 2
            obj_cy = oy + oh / 2

            if snap_edges:
                # 垂直参考线（X 对齐）
                for drag_x in (x, r):
                    for obj_x in (ox, obj_r):
                        if abs(drag_x - obj_x) < t:
                            min_y = min(y, oy) - 10
                            max_y = max(b, obj_b) + 10
                            guides.append(SnapLine(
                                position=obj_x,
                                is_horizontal=False,
                                start=min_y, end=max_y))

                # 水平参考线（Y 对齐）
                for drag_y in (y, b):
                    for obj_y in (oy, obj_b):
                        if abs(drag_y - obj_y) < t:
                            min_x = min(x, ox) - 10
                            max_x = max(r, obj_r) + 10
                            guides.append(SnapLine(
                                position=obj_y,
                                is_horizontal=True,
                                start=min_x, end=max_x))

            if snap_centers:
                # 垂直中心参考线
                if abs(cx - obj_cx) < t:
                    min_y = min(y, oy) - 10
                    max_y = max(b, obj_b) + 10
                    guides.append(SnapLine(
                        position=obj_cx,
                        is_horizontal=False,
                        start=min_y, end=max_y))

                # 水平中心参考线
                if abs(cy - obj_cy) < t:
                    min_x = min(x, ox) - 10
                    max_x = max(r, obj_r) + 10
                    guides.append(SnapLine(
                        position=obj_cy,
                        is_horizontal=True,
                        start=min_x, end=max_x))

        # 去重（相同位置和方向的参考线合并）
        return _deduplicate_guides(guides)


def _deduplicate_guides(guides: List[SnapLine]) -> List[SnapLine]:
    """合并位置相近、方向相同的参考线。"""
    if not guides:
        return []

    merged: Dict[Tuple[bool, int], SnapLine] = {}
    for g in guides:
        # 用四舍五入后的整数位置作为 key
        key = (g.is_horizontal, round(g.position))
        if key in merged:
            existing = merged[key]
            existing.start = min(existing.start, g.start)
            existing.end = max(existing.end, g.end)
        else:
            merged[key] = SnapLine(
                position=g.position,
                is_horizontal=g.is_horizontal,
                start=g.start, end=g.end,
                label=g.label)

    return list(merged.values())
