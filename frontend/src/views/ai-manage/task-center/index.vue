<script setup>
import { computed, h, onMounted, ref } from 'vue'
import {
  NAlert,
  NButton,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NPopconfirm,
  NSelect,
  NSwitch,
  NTabPane,
  NTabs,
  NTag,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { formatDateTime, renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
import api from '@/api'

defineOptions({ name: 'TaskCenter' })
const activeTab = ref('tasks')
const $taskTable = ref(null)
const $recordTable = ref(null)

const presets = ref([])
const schedulerOptions = ref([])

const taskQuery = ref({ task_name: '', task_type: null, task_enabled: null })
const recordQuery = ref({ task_name: '', task_celery_status: null })

const taskQueryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: true,
  addDelete: false,
  actionMode: 'dropdown',
}

const recordQueryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: false,
  addDelete: false,
  actionMode: 'dropdown',
}

const statusTypeMap = {
  等待执行: 'default',
  正在执行: 'info',
  成功: 'success',
  失败: 'error',
}

const schedulerLabelMap = {
  cron: 'Cron',
  interval: '固定间隔',
  datetime: '一次性',
}

const {
  modalVisible,
  modalAction,
  modalTitle,
  modalLoading,
  handleAdd,
  handleEdit,
  handleSave,
  modalForm,
  modalFormRef,
} = useCRUD({
  name: '任务',
  initForm: buildInitForm(),
  doCreate: (form) => api.createTask(buildPayload(form)),
  doUpdate: (form) => api.updateTask(buildPayload(form, true)),
  refresh: () => $taskTable.value?.handleSearch(),
})

function buildInitForm() {
  return {
    task_id: null,
    task_name: '',
    task_desc: '',
    task_type: '',
    task_celery_node: '',
    task_kwargs_text: '{}',
    task_celery_scheduler: null,
    task_interval_expr: 300,
    task_datetime_expr: '',
    task_crontabs_expr: '',
    task_enabled: false,
    preset_key: null,
    write_number: 100,
    write_message: '测试文本：通过Celery异步执行函数...',
  }
}

function configToText(obj) {
  if (!obj) return '{}'
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return '{}'
  }
}

function parseConfigText(text) {
  const trimmed = (text || '').trim()
  if (!trimmed) return {}
  return JSON.parse(trimmed)
}

function buildPayload(form, isUpdate = false) {
  const kwargs = parseConfigText(form.task_kwargs_text)
  if (form.preset_key === 'example' || form.task_type === 'example') {
    kwargs.write_number = form.write_number ?? 100
    if (form.write_message) {
      kwargs.write_message = form.write_message
    }
    delete kwargs.user_id
  }
  const payload = {
    task_name: form.task_name,
    task_desc: form.task_desc || null,
    task_type: form.task_type || null,
    task_celery_node: form.task_celery_node || null,
    task_kwargs: kwargs,
    task_celery_scheduler: form.task_celery_scheduler || null,
    task_interval_expr: form.task_celery_scheduler === 'interval' ? form.task_interval_expr : null,
    task_datetime_expr: form.task_celery_scheduler === 'datetime' ? form.task_datetime_expr : null,
    task_crontabs_expr: form.task_celery_scheduler === 'cron' ? form.task_crontabs_expr : null,
    task_enabled: !!form.task_enabled,
  }
  if (isUpdate) {
    payload.task_id = form.task_id
  }
  return payload
}

function applyPreset(presetKey) {
  const preset = presets.value.find((p) => p.preset_key === presetKey)
  if (!preset) return
  const kwargs = { ...(preset.task_kwargs || {}) }
  modalForm.value = {
    ...modalForm.value,
    preset_key: presetKey,
    task_name: preset.task_name,
    task_desc: preset.task_desc || '',
    task_type: preset.task_type,
    task_celery_node: preset.task_celery_node,
    task_kwargs_text: configToText(kwargs),
    write_number: kwargs.write_number ?? 100,
    write_message: kwargs.write_message || '测试文本：通过Celery异步执行函数...',
  }
}

function syncKwargField(key, value) {
  if (!modalForm.value.task_kwargs_text) return
  try {
    const kwargs = parseConfigText(modalForm.value.task_kwargs_text)
    if (key in kwargs) {
      kwargs[key] = value
      modalForm.value.task_kwargs_text = configToText(kwargs)
    }
  } catch {
    // ignore invalid json while typing
  }
}

const isExamplePreset = computed(
    () => modalForm.value.preset_key === 'example' || modalForm.value.task_type === 'example',
)

const formWriteNumber = computed({
  get: () => modalForm.value.write_number,
  set: (val) => {
    modalForm.value.write_number = val
    syncKwargField('write_number', val ?? 100)
  },
})

const formWriteMessage = computed({
  get: () => modalForm.value.write_message,
  set: (val) => {
    modalForm.value.write_message = val
    syncKwargField('write_message', val || '')
  },
})

const kwargsPlaceholder = computed(() => {
  return '{"write_number":100,"write_message":"测试文本：通过Celery异步执行函数..."}'
})

function openEdit(row) {
  handleEdit({
    ...row,
    task_id: row.task_id ?? row.id,
    task_kwargs_text: configToText(row.task_kwargs),
    task_celery_scheduler: row.task_celery_scheduler || null,
    write_number: row.task_kwargs?.write_number ?? 100,
    write_message: row.task_kwargs?.write_message || '',
    preset_key: null,
  })
}

function openCreateFromPreset() {
  handleAdd()
}

async function loadMeta() {
  const presetRes = await api.fetchTaskCenterPresets()
  presets.value = presetRes?.presets || []
  schedulerOptions.value = (presetRes?.schedulers || []).map((s) => ({
    label: s.label,
    value: s.value,
  }))
}

async function fetchTaskList(params) {
  const res = await api.searchTasks({
    task_name: params.task_name || undefined,
    task_type: params.task_type || undefined,
    task_enabled: params.task_enabled ?? undefined,
    page: params.page || 1,
    page_size: params.pageSize || 10,
    order: ['-updated_time'],
  })
  return { data: res.data || [], total: res.total ?? 0 }
}

async function fetchRecordList(params) {
  const res = await api.searchTaskRecords({
    task_name: params.task_name || undefined,
    task_celery_status: params.task_celery_status || undefined,
    page: params.page || 1,
    page_size: params.pageSize || 10,
    order: ['-celery_start_time', '-id'],
  })
  return { data: res.data || [], total: res.total ?? 0 }
}

async function handleRunTask(row) {
  const taskId = row.task_id ?? row.id
  try {
    await api.runTask({ task_id: taskId })
    $message.success('任务已下发执行')
    $taskTable.value?.handleSearch()
    if (activeTab.value === 'records') {
      $recordTable.value?.handleSearch()
    }
  } catch {
    // interceptor handles message
  }
}

async function handleStartTask(row) {
  const taskId = row.task_id ?? row.id
  try {
    await api.startTask({ task_id: taskId })
    $message.success('任务调度已启动')
    $taskTable.value?.handleSearch()
  } catch {
    // interceptor handles message
  }
}

async function handleStopTask(row) {
  const taskId = row.task_id ?? row.id
  try {
    await api.stopTask({ task_id: taskId })
    $message.success('任务调度已停止')
    $taskTable.value?.handleSearch()
  } catch {
    // interceptor handles message
  }
}

async function handleDeleteTask(row) {
  const taskId = row.task_id ?? row.id
  try {
    await api.deleteTask({ task_id: taskId })
    $message.success('删除成功')
    $taskTable.value?.handleSearch()
  } catch {
    // interceptor handles message
  }
}

function validateKwargs(_rule, value) {
  if (!value?.trim()) return true
  try {
    JSON.parse(value)
    return true
  } catch {
    return new Error('参数须为合法 JSON')
  }
}

function onTabChange(name) {
  activeTab.value = name
  if (name === 'records') {
    $recordTable.value?.handleSearch()
  }
}

onMounted(async () => {
  await loadMeta()
  $taskTable.value?.handleSearch()
})

const presetOptions = computed(() =>
    presets.value.map((p) => ({
      label: `${p.task_name}（${p.task_type}）`,
      value: p.preset_key,
    })),
)

const enabledOptions = [
  { label: '全部', value: null },
  { label: '已启用', value: true },
  { label: '未启用', value: false },
]

const statusFilterOptions = [
  { label: '全部', value: null },
  { label: '等待执行', value: '等待执行' },
  { label: '正在执行', value: '正在执行' },
  { label: '成功', value: '成功' },
  { label: '失败', value: '失败' },
]

const taskColumns = computed(() => [
  {
    title: '任务名称',
    key: 'task_name',
    minWidth: 140,
    ellipsis: { tooltip: true },
  },
  {
    title: '分类',
    key: 'task_type',
    width: 90,
    render(row) {
      return row.task_type || '-'
    },
  },
  {
    title: '任务版本',
    key: 'task_version',
    width: 90,
    align: 'center',
    render(row) {
      return row.task_version ?? 0
    },
  },
  {
    title: '任务调度模式',
    key: 'task_celery_scheduler',
    width: 100,
    render(row) {
      if (!row.task_celery_scheduler) return '-'
      return schedulerLabelMap[row.task_celery_scheduler] || row.task_celery_scheduler
    },
  },
  {
    title: '调度状态',
    key: 'task_enabled',
    width: 90,
    align: 'center',
    render(row) {
      return row.task_enabled
          ? h(NTag, { type: 'success', size: 'small' }, { default: () => '已启用' })
          : h(NTag, { size: 'small' }, { default: () => '未启用' })
    },
  },
  {
    title: '任务调度状态',
    key: 'task_celery_status',
    width: 100,
    align: 'center',
    render(row) {
      if (!row.task_celery_status) return '-'
      return h(
          NTag,
          { type: statusTypeMap[row.task_celery_status] || 'default', size: 'small' },
          { default: () => row.task_celery_status },
      )
    },
  },
  {
    title: '最后执行时间',
    key: 'last_execute_time',
    width: 170,
    align: 'center',
    render(row) {
      return row.last_execute_time ? formatDateTime(row.last_execute_time) : '-'
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 280,
    align: 'center',
    fixed: 'right',
    render(row) {
      const taskId = row.task_id ?? row.id
      return [
        h(
            NButton,
            { size: 'tiny', quaternary: true, type: 'primary', onClick: () => handleRunTask(row) },
            { default: () => '执行', icon: renderIcon('material-symbols:play-arrow', { size: 16 }) },
        ),
        row.task_enabled
            ? h(
                NButton,
                { size: 'tiny', quaternary: true, type: 'warning', onClick: () => handleStopTask(row) },
                { default: () => '停止', icon: renderIcon('material-symbols:pause', { size: 16 }) },
            )
            : h(
                NButton,
                { size: 'tiny', quaternary: true, type: 'success', onClick: () => handleStartTask(row) },
                { default: () => '启动', icon: renderIcon('material-symbols:play-circle', { size: 16 }) },
            ),
        h(
            NButton,
            { size: 'tiny', quaternary: true, type: 'info', onClick: () => openEdit(row) },
            { default: () => '编辑', icon: renderIcon('material-symbols:edit-outline', { size: 16 }) },
        ),
        h(
            NPopconfirm,
            { onPositiveClick: () => handleDeleteTask(row) },
            {
              trigger: () =>
                  h(
                      NButton,
                      { size: 'tiny', quaternary: true, type: 'error' },
                      { default: () => '删除', icon: renderIcon('material-symbols:delete-outline', { size: 16 }) },
                  ),
              default: () => `确定删除任务「${row.task_name}」吗？`,
            },
        ),
      ]
    },
  },
])

const recordColumns = computed(() => [
  {
    title: '任务名称',
    key: 'task_name',
    minWidth: 120,
    ellipsis: { tooltip: true },
  },
  {
    title: '任务版本',
    key: 'task_version',
    width: 90,
    align: 'center',
    render(row) {
      return row.task_version ?? '-'
    },
  },
  {
    title: 'Celery ID',
    key: 'celery_id',
    minWidth: 180,
    ellipsis: { tooltip: true },
  },
  {
    title: '任务调度状态',
    key: 'task_celery_status',
    width: 100,
    align: 'center',
    render(row) {
      return h(
          NTag,
          { type: statusTypeMap[row.task_celery_status] || 'default', size: 'small' },
          { default: () => row.task_celery_status || '-' },
      )
    },
  },
  {
    title: '开始时间',
    key: 'celery_start_time',
    width: 170,
    align: 'center',
    render(row) {
      return row.celery_start_time ? formatDateTime(row.celery_start_time) : '-'
    },
  },
  {
    title: '结束时间',
    key: 'celery_end_time',
    width: 170,
    align: 'center',
    render(row) {
      return row.celery_end_time ? formatDateTime(row.celery_end_time) : '-'
    },
  },
  {
    title: '耗时',
    key: 'celery_duration',
    width: 90,
    align: 'center',
    render(row) {
      return row.celery_duration || '-'
    },
  },
  {
    title: '摘要',
    key: 'task_summary',
    minWidth: 160,
    ellipsis: { tooltip: true },
    render(row) {
      return row.task_summary || row.task_error || '-'
    },
  },
])
</script>

<template>
  <CommonPage show-footer title="任务中心">
    <NAlert type="info" :bordered="false" class="manage-tip">
      管理 Celery 示例任务：支持立即执行、定时调度（间隔/Cron/一次性）与执行记录追踪。
      示例任务会向 Worker 工作目录写入 <code>task_example.txt</code>（默认 100 行）。
    </NAlert>

    <NTabs v-model:value="activeTab" type="line" @update:value="onTabChange">
      <NTabPane name="tasks" tab="任务管理">
        <CrudTable
            ref="$taskTable"
            v-model:query-items="taskQuery"
            :query-bar-props="taskQueryBarProps"
            :remote="true"
            :scroll-x="1100"
            :columns="taskColumns"
            :get-data="fetchTaskList"
            row-key="task_id"
            @query-bar-create="openCreateFromPreset"
        >
          <template #queryBar>
            <QueryBarItem label="任务名称：">
              <NInput
                  v-model:value="taskQuery.task_name"
                  clearable
                  placeholder="模糊搜索"
                  @keypress.enter="$taskTable?.handleSearch()"
              />
            </QueryBarItem>
            <QueryBarItem label="调度状态：">
              <NSelect
                  v-model:value="taskQuery.task_enabled"
                  :options="enabledOptions"
                  clearable
                  style="width: 120px"
              />
            </QueryBarItem>
          </template>
        </CrudTable>
      </NTabPane>

      <NTabPane name="records" tab="执行记录">
        <CrudTable
            ref="$recordTable"
            v-model:query-items="recordQuery"
            :query-bar-props="recordQueryBarProps"
            :remote="true"
            :scroll-x="1000"
            :columns="recordColumns"
            :get-data="fetchRecordList"
            row-key="record_id"
        >
          <template #queryBar>
            <QueryBarItem label="任务名称：">
              <NInput
                  v-model:value="recordQuery.task_name"
                  clearable
                  placeholder="模糊搜索"
                  @keypress.enter="$recordTable?.handleSearch()"
              />
            </QueryBarItem>
            <QueryBarItem label="任务调度状态：">
              <NSelect
                  v-model:value="recordQuery.task_celery_status"
                  :options="statusFilterOptions"
                  clearable
                  style="width: 120px"
              />
            </QueryBarItem>
          </template>
        </CrudTable>
      </NTabPane>
    </NTabs>

    <CrudModal
        v-model:visible="modalVisible"
        :title="modalTitle"
        :loading="modalLoading"
        width="720px"
        @save="handleSave"
    >
      <NForm
          ref="modalFormRef"
          label-placement="left"
          label-align="left"
          :label-width="100"
          :model="modalForm"
          :disabled="modalAction === 'view'"
      >
        <NFormItem v-if="modalAction === 'add'" label="任务模板" path="preset_key">
          <NSelect
              v-model:value="modalForm.preset_key"
              :options="presetOptions"
              clearable
              placeholder="选择模板快速填充"
              @update:value="applyPreset"
          />
        </NFormItem>
        <NFormItem
            label="任务名称"
            path="task_name"
            :rule="{ required: true, message: '请输入任务名称', trigger: ['input', 'blur'] }"
        >
          <NInput v-model:value="modalForm.task_name" placeholder="任务显示名称" />
        </NFormItem>
        <NFormItem label="任务描述" path="task_desc">
          <NInput v-model:value="modalForm.task_desc" type="textarea" :rows="2" placeholder="可选" />
        </NFormItem>
        <NFormItem label="任务分类" path="task_type">
          <NInput v-model:value="modalForm.task_type" placeholder="如 example、rag" />
        </NFormItem>
        <NFormItem
            label="任务调度节点"
            path="task_celery_node"
            :rule="{ required: true, message: '请填写任务调度节点', trigger: ['input', 'blur'] }"
        >
          <NInput v-model:value="modalForm.task_celery_node" placeholder="backend.celery_scheduler.tasks..." />
        </NFormItem>
        <NFormItem
            v-if="isExamplePreset"
            label="写入行数"
            path="write_number"
        >
          <NInputNumber
              v-model:value="formWriteNumber"
              :min="1"
              :max="100"
              :step="10"
              style="width: 100%"
          />
        </NFormItem>
        <NFormItem
            v-if="isExamplePreset"
            label="写入内容"
            path="write_message"
        >
          <NInput
              v-model:value="formWriteMessage"
              type="textarea"
              :rows="2"
              placeholder="测试文本：通过Celery异步执行函数..."
          />
        </NFormItem>
        <NFormItem
            label="执行参数"
            path="task_kwargs_text"
            :rule="{ validator: validateKwargs, trigger: ['input', 'blur'] }"
        >
          <NInput
              v-model:value="modalForm.task_kwargs_text"
              type="textarea"
              :rows="6"
              :placeholder="kwargsPlaceholder"
          />
        </NFormItem>
        <NFormItem label="任务调度模式" path="task_celery_scheduler">
          <NSelect
              v-model:value="modalForm.task_celery_scheduler"
              :options="schedulerOptions"
              clearable
              placeholder="不选则仅支持手动执行"
          />
        </NFormItem>
        <NFormItem v-if="modalForm.task_celery_scheduler === 'interval'" label="间隔(秒)" path="task_interval_expr">
          <NInputNumber v-model:value="modalForm.task_interval_expr" :min="10" :step="10" style="width: 100%" />
        </NFormItem>
        <NFormItem v-if="modalForm.task_celery_scheduler === 'cron'" label="Cron表达式" path="task_crontabs_expr">
          <NInput v-model:value="modalForm.task_crontabs_expr" placeholder="如 0 */2 * * *" />
        </NFormItem>
        <NFormItem v-if="modalForm.task_celery_scheduler === 'datetime'" label="执行时间" path="task_datetime_expr">
          <NInput v-model:value="modalForm.task_datetime_expr" placeholder="YYYY-MM-DD HH:MM:SS" />
        </NFormItem>
        <NFormItem label="启用调度" path="task_enabled">
          <NSwitch v-model:value="modalForm.task_enabled" />
        </NFormItem>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>

<style scoped>
.manage-tip {
  margin-bottom: 12px;
}
.manage-tip code {
  font-size: 12px;
  background: rgba(0, 0, 0, 0.06);
  padding: 1px 4px;
  border-radius: 3px;
}
</style>
