"""Accessible overview of the modelling workflow, shared by learning pages."""

import re


def method_flow() -> str:
    return '''<section class="method-flow" data-method-flow aria-labelledby="method-flow-title">
      <div class="method-flow__heading"><div><p class="eyebrow">计算方法 · 从基准到采样</p><h2 id="method-flow-title">精度、尺度与算力，怎样取舍？</h2></div><span class="method-flow__label">DFT → AIMD → MLIP</span></div>
      <ol class="method-flow__nodes">
        <li><a class="method-flow__node" href="./foundations.html#topic-ks"><span class="method-flow__index">01 / 电子结构</span><h3>DFT</h3><p>求解电子结构，为能量、力与应力建立参考。</p><dl><dt>尺度</dt><dd>局部结构与静态基准</dd><dt>算力</dt><dd>每次求力成本较高</dd><dt>检查</dt><dd>泛函、截断能与 k 点收敛</dd></dl></a></li>
        <li><a class="method-flow__node" href="./foundations.html#topic-md"><span class="method-flow__index">02 / 有限温度</span><h3>AIMD</h3><p>逐步计算第一性原理力，观察原子热运动。</p><dl><dt>尺度</dt><dd>有限体系与有限轨迹</dd><dt>算力</dt><dd>逐步求力，采样代价累积</dd><dt>检查</dt><dd>步长、系综与统计采样</dd></dl></a></li>
        <li><a class="method-flow__node" href="./foundations.html#topic-mlip"><span class="method-flow__index">03 / 扩展采样</span><h3>MLIP</h3><p>学习参考势能面，将计算预算用于更长、更大尺度的 MD。</p><dl><dt>尺度</dt><dd>更大体系与更长轨迹</dd><dt>算力</dt><dd>标注与训练投入，推断较快</dd><dt>检查</dt><dd>目标域误差与分布外验证</dd></dl></a></li>
      </ol>
      <p class="method-flow__note">箭头表示工作流衔接。AIMD 的力可来自 DFT；MLIP 的可信范围取决于参考方法、训练覆盖和目标域验证，计算尺度扩大并不自动提高精度。</p>
    </section>'''


def prepare_method_flow(source: str, page: str) -> str:
    """Replace the previous generated overview so repeated builds stay stable."""
    source = re.sub(r'<section\b[^>]*\bdata-method-flow\b[^>]*>.*?</section>\s*', '', source, flags=re.S)
    if page in {'foundations.html', 'learning-route.html'}:
        source = re.sub(r'(<main\b[^>]*>)', lambda match: match[1] + method_flow(), source, count=1)
    return source
