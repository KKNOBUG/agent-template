<script setup>
import { computed, h, onMounted, ref } from 'vue'
import {
  NAlert,
  NButton,
  NForm,
  NFormItem,
  NInput,
  NPopconfirm,
  NSelect,
  NSwitch,
  NTag,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { formatDateTime, renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
import api from '@/api'

defineOptions({ name: 'McpManage' })

const transportOptions = [
  { label: 'stdio', value: 'stdio' },
  { label: 'sse', value: 'sse' },
  { label: 'http', value: 'http' },
]

const $table = ref(null)
const queryItems = ref({ name: '' })

const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: true,
  addDelete: false,
  actionMode: 'dropdown',
}

const {
  modalVisible,
  modalAction,
  modalTitle,
  modalLoading,
  handleAdd,
  handleDelete,
  handleEdit,
  handleSave,
  modalForm,
  modalFormRef,
} = useCRUD({
  name: 'MCP 服务',
  initForm: {
    name: '',
    description: '',
    transport: 'stdio',
    is_enabled: true,
    config_text: '',
  },
  doCreate: (form) => api.createMcpServer(buildPayload(form)),
  doDelete: (params) => api.deleteMcpServer(params.id),
  doUpdate: (form) => api.updateMcpServer(form.id, buildPayload(form)),
  refresh: () => $table.value?.handleSearch(),
})

function configToText(config) {
  if (!config) return ''
  try {
    return JSON.stringify(config, null, 2)
  } catch {
    return ''
  }
}

function parseConfigText(text) {
  const trimmed = (text || '').trim()
  if (!trimmed) return null
  return JSON.parse(trimmed)
}

function buildPayload(form) {
  return {
    name: form.name,
    description: form.description || null,
    transport: form.transport || 'stdio',
    is_enabled: !!form.is_enabled,
    config: parseConfigText(form.config_text),
  }
}

function openEdit(row) {
  handleEdit({
    ...row,
    config_text: configToText(row.config),
  })
}

async function fetchMcpList(params) {
  const list = await api.fetchMcpServers('', true)
  const kw = (params.name || '').trim()
  const filtered = kw
      ? list.filter((item) => item.name.includes(kw) || (item.description || '').includes(kw))
      : list
  return { data: filtered, total: filtered.length }
}

function validateConfig(_rule, value) {
  if (!value?.trim()) return true
  try {
    JSON.parse(value)
    return true
  } catch {
    return new Error('配置须为合法 JSON')
  }
}

onMounted(() => {
  $table.value?.handleSearch()
})

const columns = computed(() => [
  {
    title: '服务名称',
    key: 'name',
    minWidth: 140,
    ellipsis: { tooltip: true },
  },
  {
    title: '传输方式',
    key: 'transport',
    width: 100,
    align: 'center',
    render(row) {
      return h(NTag, { size: 'small' }, { default: () => row.transport || 'stdio' })
    },
  },
  {
    title: '描述',
    key: 'description',
    minWidth: 180,
    ellipsis: { tooltip: true },
    render(row) {
      return row.description || '-'
    },
  },
  {
    title: '状态',
    key: 'is_enabled',
    width: 90,
    align: 'center',
    render(row) {
      return row.is_enabled
          ? h(NTag, { type: 'success', size: 'small' }, { default: () => '启用' })
          : h(NTag, { size: 'small' }, { default: () => '禁用' })
    },
  },
  {
    title: '创建时间',
    key: 'created_time',
    width: 170,
    align: 'center',
    render(row) {
      return formatDateTime(row.created_time)
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 160,
    align: 'center',
    fixed: 'right',
    render(row) {
      return [
        h(
            NButton,
            {
              size: 'tiny',
              quaternary: true,
              type: 'info',
              onClick: () => openEdit(row),
            },
            {
              default: () => '编辑',
              icon: renderIcon('material-symbols:edit-outline', { size: 16 }),
            },
        ),
        h(
            NPopconfirm,
            {
              onPositiveClick: () => handleDelete({ id: row.id }),
            },
            {
              trigger: () =>
                  h(
                      NButton,
                      {
                        size: 'tiny',
                        quaternary: true,
                        type: 'error',
                      },
                      {
                        default: () => '删除',
                        icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
                      },
                  ),
              default: () => '确定删除该 MCP 服务吗？',
            },
        ),
      ]
    },
  },
])
</script>

<template>
  <CommonPage show-footer title="MCP 管理">
    <NAlert type="info" :bordered="false" class="manage-tip">
      管理 MCP 服务连接配置。仅「启用」状态的服务会出现在聊天页选择器中；config 为 JSON，stdio 示例：
      <code>{"command":"npx","args":["-y","@modelcontextprotocol/server-filesystem","/path"]}</code>
    </NAlert>
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :query-bar-props="queryBarProps"
        :is-pagination="true"
        :remote="false"
        :scroll-x="960"
        :columns="columns"
        :get-data="fetchMcpList"
        row-key="id"
        @query-bar-create="handleAdd"
    >
      <template #queryBar>
        <QueryBarItem label="服务名称：">
          <NInput
              v-model:value="queryItems.name"
              clearable
              placeholder="请输入服务名称或描述"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <CrudModal
        v-model:visible="modalVisible"
        :title="modalTitle"
        :loading="modalLoading"
        width="640px"
        @save="handleSave"
    >
      <NForm
          ref="modalFormRef"
          label-placement="left"
          label-align="left"
          :label-width="90"
          :model="modalForm"
          :disabled="modalAction === 'view'"
      >
        <NFormItem
            label="服务名称"
            path="name"
            :rule="{ required: true, message: '请输入服务名称', trigger: ['input', 'blur'] }"
        >
          <NInput v-model:value="modalForm.name" placeholder="如：文件系统 MCP" />
        </NFormItem>
        <NFormItem label="传输方式" path="transport">
          <NSelect
              v-model:value="modalForm.transport"
              :options="transportOptions"
              placeholder="选择传输方式"
          />
        </NFormItem>
        <NFormItem label="服务描述" path="description">
          <NInput
              v-model:value="modalForm.description"
              type="textarea"
              :rows="2"
              placeholder="可选，描述该 MCP 服务能力"
          />
        </NFormItem>
        <NFormItem label="是否启用" path="is_enabled">
          <NSwitch v-model:value="modalForm.is_enabled" />
        </NFormItem>
        <NFormItem
            label="连接配置"
            path="config_text"
            :rule="{ validator: validateConfig, trigger: ['input', 'blur'] }"
        >
          <NInput
              v-model:value="modalForm.config_text"
              type="textarea"
              :rows="8"
              placeholder='JSON，stdio 示例：{"command":"npx","args":["-y","@modelcontextprotocol/server-filesystem","/tmp"]}'
          />
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
  word-break: break-all;
}
</style>
