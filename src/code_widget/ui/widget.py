"""挂件窗口（M2）：收起态大肥鱼贴纸 + 展开态完整列表面板。

- 收起态：fish_alpha.png 贴纸，左上气泡内渲染最新兑换码摘要；按压缩放回弹动画
- 展开态：ExpandedPanel（深色半透明圆角面板，见 ui/panel.py）
- 拖拽移动 + 四边贴边吸附（动画，F9）；双击切换收起/展开（F4/F5）
- 关闭窗口 = 隐藏到托盘（F10，真正退出走托盘菜单）
- 红线：本文件不做任何网络/文件 IO，数据仅经 CodeService 信号推送
  （加载自身图片素材属于 UI 职责，不算业务 IO）
"""
from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, QPoint, QPointF, QPropertyAnimation,
                            QRectF, Qt, QTimer, Signal)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from ..core.models import CodeItem
from .panel import EXPANDED_SIZE, MIN_EXPANDED_SIZE, ExpandedPanel
from .tray import asset

DRAG_THRESHOLD = 6   # px，鼠标位移超过该值视为拖拽而非点击
BASE_SIZE = 300      # 收起态基准边长（乘 ui.scale）


class BubbleFrame(QWidget):
    """代码绘制的思考气泡（仿 Dsh 大肥鱼挂件 v0.2.5：本体与气泡素材分离）。

    白底 + 深蓝描边圆角气泡 + 两个引导圆点（指向右下角的鱼本体）；
    文字为子 QLabel。显示/隐藏即本控件 setVisible。
    """

    OUTLINE = "#2B4A78"

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.text = QLabel(self)
        self.text.setWordWrap(True)
        self.text.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.text.setStyleSheet(
            "color:#22436B; font-size:12px; font-weight:600; background:transparent;")

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = float(self.width()), float(self.height())
        pen_w = max(3.0, h * 0.030)
        body = QRectF(pen_w, pen_w, w - pen_w * 2, h * 0.80 - pen_w)
        path = QPainterPath()
        path.addRoundedRect(body, body.height() * 0.38, body.height() * 0.38)
        p.setPen(QPen(QColor(self.OUTLINE), pen_w))
        p.setBrush(QColor(255, 255, 255, 250))
        p.drawPath(path)
        p.setBrush(QColor(255, 255, 255, 250))
        # 引导圆点须完整落在控件内：圆心+半径+半描边 ≤ 边界，否则会被裁剪
        for cx, cy, r in ((w * 0.84, h * 0.885, h * 0.048),
                          (w * 0.935, h * 0.945, h * 0.030)):
            p.drawEllipse(QPointF(cx, cy), r, r)

    def resizeEvent(self, e) -> None:
        w, h = self.width(), self.height()
        self.text.setGeometry(int(w * 0.11), int(h * 0.12),
                              int(w * 0.78), int(h * 0.60))

    def set_text(self, s: str) -> None:
        self.text.setText(s)


class CollapsedFishView(QWidget):
    """收起态：左列代码绘制气泡 + 右列大肥鱼本体贴图，两区域互不重叠。

    布局在 resizeEvent 里按素材比例动态计算；气泡默认隐藏（单击鱼身弹出）。
    """

    def __init__(self, parent: QWidget, bubble_seconds: int = 5):
        super().__init__(parent)
        path = asset("fish_body.png")             # 分离后的纯本体贴图
        if not path.exists():                     # 回退：带气泡整图抠图版
            path = asset("fish_alpha.png")
        if not path.exists():                     # 再回退：白底原图
            path = asset("fish.png")
        self._source = QPixmap(str(path))
        self.sticker = QLabel(self)
        self.sticker.setStyleSheet("background: transparent;")
        self.bubble = BubbleFrame(self)
        self.bubble.hide()    # 默认隐藏：单击鱼身弹出，再点收起（参考鲸鱼挂件）
        self._bubble_seconds = max(0, int(bubble_seconds))
        self._bubble_timer = QTimer(self)
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.timeout.connect(self.bubble.hide)
        self._anims: tuple = ()

    def preferred_size(self, scale: float = 1.0) -> tuple[int, int]:
        """收起态窗口推荐尺寸：气泡列 + 缝隙 + 鱼本体列（随素材比例与缩放）。"""
        s = min(2.5, max(0.6, scale))
        fish_h = int(BASE_SIZE * 0.88 * s)
        fish_w = int(fish_h * self._source.width() / max(1, self._source.height()))
        bubble_w = int(BASE_SIZE * 0.63 * s)
        return (bubble_w + fish_w + 26, fish_h + 14)

    def resizeEvent(self, e) -> None:
        w, h = self.width(), self.height()
        # 鱼本体列：高占满（留边距），宽按素材比例，右下角锚定
        pm_h = h - 10
        pm_w = int(pm_h * self._source.width() / max(1, self._source.height()))
        dpr = self.devicePixelRatioF() or 1.0
        pm = self._source.scaled(
            int(pm_w * dpr), int(pm_h * dpr), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pm.setDevicePixelRatio(dpr)
        self.sticker.setPixmap(pm)
        fx = w - pm_w - 5
        self.sticker.setGeometry(fx, h - pm_h - 5, pm_w, pm_h)
        # 气泡列：只占本体左侧的空白区，绝不压到人物
        bw = max(120, min(fx - 16, int(w * 0.44)))
        bh = int(bw * 0.78)
        self.bubble.setGeometry(8, max(8, (h - bh) // 2 - 6), bw, min(bh, h - 16))

    def set_bubble(self, text: str) -> None:
        self.bubble.set_text(text)

    def set_tooltip(self, text: str) -> None:
        self.sticker.setToolTip(text)

    def show_bubble(self) -> None:
        self.bubble.show()
        if self._bubble_seconds > 0:
            self._bubble_timer.start(self._bubble_seconds * 1000)
        else:
            self._bubble_timer.stop()             # 0 = 常驻，再点一次收起

    def hide_bubble(self) -> None:
        self._bubble_timer.stop()
        self.bubble.hide()

    def toggle_bubble(self) -> None:
        if self.bubble.isVisible():
            self.hide_bubble()
        else:
            self.show_bubble()

    def squash(self) -> None:
        """按压 Q 弹：底部锚定，先压缩再回弹（创意移植自鲸鱼挂件）。"""
        if self._anims and self._anims[0].state() == QPropertyAnimation.Running:
            return
        s = self.sticker
        full = s.geometry()
        pressed = full.adjusted(0, int(full.height() * 0.08), 0, 0)
        down = QPropertyAnimation(s, b"geometry", self)
        down.setDuration(90)
        down.setEndValue(pressed)
        down.setEasingCurve(QEasingCurve.InQuad)
        up = QPropertyAnimation(s, b"geometry", self)
        up.setDuration(260)
        up.setEndValue(full)
        up.setEasingCurve(QEasingCurve.OutBack)
        down.finished.connect(up.start)
        self._anims = (down, up)   # 持引用防 GC
        down.start()


class WidgetWindow(QWidget):
    """无边框半透明置顶挂件：收起态 ↔ 展开态，拖拽 + 贴边吸附。"""

    # 对外（业务层）信号：View 只发意图，不执行 IO
    refreshRequested = Signal()
    markRequested = Signal(str, object)   # uid, status|None
    visibilityToggled = Signal(bool)

    def __init__(self, cfg):
        flags = Qt.FramelessWindowHint | Qt.Tool
        if cfg.get("ui.always_on_top", True):
            flags |= Qt.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._cfg = cfg
        self.setWindowOpacity(float(cfg.get("ui.opacity", 0.95)))

        self._expanded = False
        self._drag_offset = QPoint()
        self._dragging = False
        self._snap_anim = None
        self._ctx_menu = None
        self._items: list[CodeItem] = []

        self._ui_scale = min(2.5, max(0.6, float(cfg.get("ui.scale", 1.0))))

        self._panel = ExpandedPanel(self)
        self._collapsed = CollapsedFishView(
            self, bubble_seconds=int(cfg.get("ui.bubble_seconds", 5)))
        self._panel.collapseRequested.connect(self.toggle_expand)
        self._panel.hide()
        self._collapsed_size = self._collapsed.preferred_size(self._ui_scale)
        self.resize(*self._collapsed_size)

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key_Escape:
            if self._expanded:
                self.toggle_expand()      # Esc：详情返回小肥鱼
            else:
                self.hide()               # Esc：挂件隐藏到托盘
            return
        super().keyPressEvent(e)

    # ---------- 数据推送（main.py 与 CodeService 信号接线） ----------
    def on_codes_updated(self, items: list[CodeItem]) -> None:
        self._items = list(items)
        alive = [it for it in self._items if not it.is_expired and not it.is_redeemed]
        if alive:
            latest = alive[0]   # 数据仓库约定：新码在数组前部
            self._collapsed.set_bubble(f"{latest.game_name} 新码\n{latest.code}")
            self._collapsed.set_tooltip("\n".join(
                f"{it.game_name}  {it.code}" for it in alive[:3]))
        elif self._items:
            self._collapsed.set_bubble("暂无可用新码\n双击展开列表")
        else:
            self._collapsed.set_bubble("还没有数据\n等首次更新…")
        self._panel.set_items(self._items)

    def on_fetch_started(self) -> None:
        self._panel.set_status("● 正在检查更新…", "#7FB7E8")

    def on_fetch_finished(self, ok: bool, msg: str) -> None:
        self._panel.set_status(f"● {msg}", "#7BD8A5" if ok else "#F2B662")

    def on_new_codes(self, new_items: list[CodeItem]) -> None:
        names = "、".join(it.game_name for it in new_items[:3])
        more = f" 等{len(new_items)}个" if len(new_items) > 3 else ""
        self._collapsed.set_bubble(f"有新码啦！\n{names}{more}")
        self._collapsed.show_bubble()   # 有新码时主动冒泡一次，随后自动收起
        QTimer.singleShot(5000, lambda: self.on_codes_updated(self._items))

    # ---------- 展开/收起（双击鱼） ----------
    def _expanded_size(self) -> tuple[int, int]:
        """上次的展开尺寸（记忆于 config），并限制在合理范围内。"""
        raw = self._cfg.get("ui.expanded_size") or []
        try:
            w, h = int(raw[0]), int(raw[1])
        except (TypeError, IndexError, ValueError):
            w, h = EXPANDED_SIZE
        return (min(1000, max(MIN_EXPANDED_SIZE[0], w)),
                min(1400, max(MIN_EXPANDED_SIZE[1], h)))

    def toggle_expand(self) -> None:
        self._expanded = not self._expanded
        if self._expanded:
            # 最小尺寸设在窗口上（角托拖的是窗口），防止拖得比面板最小值还小、
            # 面板右侧溢出被裁（圆角与角托消失）
            self.setMinimumSize(*MIN_EXPANDED_SIZE)
            self.resize(*self._expanded_size())
        else:
            cur = self.size()   # 记住用户用角托调整后的尺寸
            if (cur.width(), cur.height()) != self._collapsed_size:
                self._cfg.set("ui.expanded_size", [cur.width(), cur.height()])
                self._cfg.save()
            self.setMinimumSize(0, 0)   # 收起态解除限制
            self.resize(*self._collapsed_size)
        self._collapsed.setVisible(not self._expanded)
        self._panel.setVisible(self._expanded)
        self._clamp_into_screen()

    def toggle(self) -> None:
        self.setVisible(not self.isVisible())
        self.visibilityToggled.emit(self.isVisible())

    def set_context_menu(self, menu) -> None:
        """复用托盘菜单（F10）：挂件本体右键与托盘右键等价。"""
        self._ctx_menu = menu

    def contextMenuEvent(self, e) -> None:
        if self._ctx_menu is not None:
            self._ctx_menu.exec(e.globalPos())

    def apply_ui_settings(self, cfg) -> None:
        """设置页保存后热生效：透明度/置顶/缩放（吸附阈值等在使用时实时读取）。"""
        self._cfg = cfg
        self.setWindowOpacity(float(cfg.get("ui.opacity", 0.95)))
        on_top = bool(cfg.get("ui.always_on_top", True))
        if bool(self.windowFlags() & Qt.WindowStaysOnTopHint) != on_top:
            was_visible = self.isVisible()
            self.setWindowFlag(Qt.WindowStaysOnTopHint, on_top)   # 会隐藏窗口
            if was_visible:
                self.show()
        self._ui_scale = min(2.5, max(0.6, float(cfg.get("ui.scale", 1.0))))
        self._collapsed_size = self._collapsed.preferred_size(self._ui_scale)
        if not self._expanded:
            self.resize(*self._collapsed_size)
        self._clamp_into_screen()

    def closeEvent(self, e) -> None:
        e.ignore()          # 关闭 = 隐藏到托盘，不退出
        self.hide()
        self.visibilityToggled.emit(False)

    def resizeEvent(self, e) -> None:
        r = self.rect()
        self._collapsed.setGeometry(r)
        self._panel.setGeometry(r)

    # ---------- 拖拽 + 吸附（F9） ----------
    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self._drag_offset = e.globalPosition().toPoint() - self.pos()
            self._dragging = False
            if self._collapsed.isVisible():
                self._collapsed.squash()

    def mouseMoveEvent(self, e) -> None:
        if not (e.buttons() & Qt.LeftButton) or self._drag_offset.isNull():
            return
        gp = e.globalPosition().toPoint()
        if not self._dragging:
            delta = gp - (self.pos() + self._drag_offset)
            if delta.manhattanLength() > DRAG_THRESHOLD:
                self._dragging = True
        if self._dragging:
            self.move(gp - self._drag_offset)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() != Qt.LeftButton:
            return
        if self._dragging and self._cfg.get("ui.snap_enabled", True):
            self._snap_to_edge()
        elif not self._dragging and self._collapsed.isVisible():
            self._collapsed.toggle_bubble()   # 单击鱼身：弹出/收起气泡
        self._dragging = False
        self._drag_offset = QPoint()

    def mouseDoubleClickEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self.toggle_expand()

    def _available_screen(self):
        scr = QApplication.screenAt(self.geometry().center())
        return (scr or QApplication.primaryScreen()).availableGeometry()

    def _snap_to_edge(self) -> None:
        """距屏幕四边小于阈值时吸附到 edge_margin_px 处（动画过渡）。"""
        scr = self._available_screen()
        g = self.geometry()
        th = int(self._cfg.get("ui.snap_threshold_px", 24))
        mg = int(self._cfg.get("ui.edge_margin_px", 8))
        x, y = g.x(), g.y()
        if g.left() - scr.left() < th:
            x = scr.left() + mg
        elif scr.right() - g.right() < th:
            x = scr.right() - g.width() + 1 - mg
        if g.top() - scr.top() < th:
            y = scr.top() + mg
        elif scr.bottom() - g.bottom() < th:
            y = scr.bottom() - g.height() + 1 - mg
        if (x, y) == (g.x(), g.y()):
            return
        anim = QPropertyAnimation(self, b"pos", self)
        anim.setDuration(150)
        anim.setEndValue(QPoint(x, y))
        anim.setEasingCurve(QEasingCurve.OutCubic)
        self._snap_anim = anim   # 持引用防 GC
        anim.start()

    def _clamp_into_screen(self) -> None:
        scr = self._available_screen()
        g = self.geometry()
        x = min(max(g.x(), scr.left()), scr.right() - g.width() + 1)
        y = min(max(g.y(), scr.top()), scr.bottom() - g.height() + 1)
        self.move(x, y)
