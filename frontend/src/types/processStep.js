/** 前后端约定的 process_trace step 结构 */

export const STEP_TYPES = {
  REASONING: 'reasoning',
  SKILL: 'skill',
  MCP: 'mcp',
}

export const STEP_STATUS = {
  RUNNING: 'running',
  DONE: 'done',
  ERROR: 'error',
}

export const STEP_TYPE_LABELS = {
  [STEP_TYPES.REASONING]: '深度思考',
  [STEP_TYPES.SKILL]: '技能调用',
  [STEP_TYPES.MCP]: 'MCP 工具',
}

export function createReasoningStep(content = '') {
  return { type: STEP_TYPES.REASONING, status: STEP_STATUS.RUNNING, content }
}

export function createSkillStep({ skillId, name, input } = {}) {
  return {
    type: STEP_TYPES.SKILL,
    status: STEP_STATUS.RUNNING,
    skill_id: skillId || null,
    name: name || null,
    input: input || null,
    output: null,
  }
}

export function createMcpStep({ server, tool, arguments: args } = {}) {
  return {
    type: STEP_TYPES.MCP,
    status: STEP_STATUS.RUNNING,
    server: server || null,
    tool: tool || null,
    arguments: args || null,
    result: null,
  }
}

export function isStepVisible(step) {
  if (!step) return false
  if (step.status === STEP_STATUS.RUNNING) return true
  if (step.type === STEP_TYPES.REASONING) return !!step.content
  if (step.type === STEP_TYPES.SKILL) return !!(step.output || step.input || step.name)
  if (step.type === STEP_TYPES.MCP) return !!(step.result || step.arguments || step.tool)
  return !!(step.content || step.title)
}

export function stepLabel(step) {
  if (step.type === STEP_TYPES.REASONING) return STEP_TYPE_LABELS.reasoning
  if (step.type === STEP_TYPES.SKILL) return step.name || STEP_TYPE_LABELS.skill
  if (step.type === STEP_TYPES.MCP) {
    if (step.tool) return `${step.server || 'MCP'} · ${step.tool}`
    return step.server || STEP_TYPE_LABELS.mcp
  }
  return step.title || '处理过程'
}

export function stepIcon(step) {
  if (step.type === STEP_TYPES.SKILL) return 'hugeicons:ai-magic'
  if (step.type === STEP_TYPES.MCP) return 'hugeicons:plug-socket'
  return 'hugeicons:brain-02'
}

export function formatJsonBlock(value) {
  if (value == null || value === '') return ''
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}
