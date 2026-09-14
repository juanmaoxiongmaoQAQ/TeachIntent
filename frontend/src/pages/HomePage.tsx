import {
  ArrowRight,
  BookOpen,
  MessageSquareText,
  Sparkles,
} from "lucide-react";

export function HomePage() {
  return (
    <div className="home-page">
      <section className="home-hero">
        <div>
          <p className="eyebrow">让每一次教学回应，都有明确的意图</p>
          <h1>
            教学意图驱动的
            <br />
            AI 教学语音规划
          </h1>
          <p className="hero-description">
            根据教学内容、学生状态和教学意图，
            <br className="desktop-break" />
            规划 AI 教师“说什么”和“怎么说”。
          </p>
          <div className="hero-actions">
            <a className="button-primary" href="/studio">
              开始体验 <ArrowRight size={17} aria-hidden="true" />
            </a>
            <a className="button-secondary" href="/examples">
              查看示例
            </a>
          </div>
          <p className="subtle">先看懂教学计划，再决定是否生成语音。</p>
        </div>
        <div className="hero-preview" aria-label="输入与输出示意">
          <div className="preview-input">
            <MessageSquareText size={20} aria-hidden="true" />
            <div>
              <span className="eyebrow">学生当前回答</span>
              <p>
                “我觉得 1/4 比 1/3 大，
                <br />
                因为 4 比 3 大。”
              </p>
            </div>
          </div>
          <div className="preview-intent">
            教学意图 <strong>纠错反馈</strong>
          </div>
          <div className="preview-plan">
            <span className="eyebrow">教学语音计划 · 示意</span>
            <p>
              <span>01</span> 先认可学生的观察 <small>柔和</small>
            </p>
            <p>
              <span>02</span> 澄清分母的含义 <small>自然</small>
            </p>
            <p>
              <span>03</span> 解释每一份的大小 <small>自然</small>
            </p>
            <p>
              <span>04</span> 强调最终结论 <small>强调</small>
            </p>
          </div>
          <a href="/studio?example=fractions" className="text-link">
            用这个场景开始体验 <ArrowRight size={15} aria-hidden="true" />
          </a>
        </div>
      </section>
      <section className="home-flow" aria-label="核心流程">
        <div className="section-heading">
          <div>
            <p className="eyebrow">从教学情况，到可检查的计划</p>
            <h2>先规划怎样教，再决定怎样说</h2>
          </div>
          <p className="subtle">表达方式与教学目标一起被明确规划。</p>
        </div>
        <ol className="flow-steps">
          <li>
            <BookOpen size={22} aria-hidden="true" />
            <strong>教学情况</strong>
            <p>教学内容 · 学生状态 · 教学意图</p>
          </li>
          <li>
            <Sparkles size={22} aria-hidden="true" />
            <strong>Hy3 规划</strong>
            <p>形成有针对性的教学回应</p>
          </li>
          <li>
            <MessageSquareText size={22} aria-hidden="true" />
            <strong>教学语音计划</strong>
            <p>说什么 + 怎么说</p>
          </li>
          <li>
            <strong>计划质量检查</strong>
            <p>检查 Speech Plan，不评价音频</p>
          </li>
          <li>
            <strong>可选语音生成</strong>
            <p>把教学计划转成可试听的表达</p>
          </li>
        </ol>
      </section>
      <section className="home-explanation">
        <div>
          <p className="eyebrow">不止于一段回答</p>
          <h2>教学意图，让表达有依据</h2>
          <p>
            从文本直接到语音，教学策略和表达方式往往隐藏在一句指令里。TeachIntent
            把学生需要什么帮助、每一步说什么、哪里需要调整表达写进同一份结构化计划，方便查看、检查和执行。
          </p>
        </div>
        <div>
          <h3>用真实示例，看见规划的差别</h3>
          <p>
            纠错时回应误解，支架中保留思考空间，支持性反馈认可具体进步。没有必要时，也可以不增加表达控制。
          </p>
          <a href="/examples?case=corrective-feedback" className="text-link">
            查看完整示例 <ArrowRight size={16} aria-hidden="true" />
          </a>
          <p className="subtle">示例库使用已有公开结果，无需模型服务。</p>
        </div>
      </section>
    </div>
  );
}
