"""自适应早停的纯判据函数。

单独成模块、无重依赖,便于在任意 Python 版本下独立单测
(引擎主体依赖 Python 3.10+ 的类型语法,不适合被测试直接导入)。
"""


def _should_stop(hist, window, min_gap):
    """判断是否应自适应早停。

    hist 是逐代 checkpoint 记录的 best-so-far 目标值列表(越小越好)。
    当最近 window 代内 best-so-far 的相对改进 (prev-cur)/prev 低于 min_gap 时返回 True。
    历史不足 window+1 个点、或端点缺失/非正,均返回 False(继续进化)。

    参数:
        hist: best-so-far 目标值序列(按 checkpoint 顺序)。
        window: 观察窗口的代数。
        min_gap: 相对改进阈值,低于它则判定平台。
    返回:
        bool,True 表示应停止进化。
    """
    if window < 1 or len(hist) <= window:
        return False
    prev = hist[-1 - window]
    cur = hist[-1]
    if prev is None or cur is None or not (prev > 0):
        return False
    gap = (prev - cur) / prev
    return gap < min_gap
