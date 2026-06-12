<script setup>
import { computed, h, onMounted, ref } from 'vue'
import {
  NAlert,
  NButton,
  NForm,
  NFormItem,
  NInput,
  NPopconfirm,
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

defineOptions({ name: 'SkillsManage' })

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
  name: '技能',
  initForm: {
    name: '',
    description: '',
    is_enabled: true,
    config_text: '',
  },
  doCreate: (form) => api.createSkill(buildPayload(form)),
  doDelete: (params) => api.deleteSkill(params.id),
  doUpdate: (form) => api.updateSkill(form.id, buildPayload(form)),
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

async function fetchSkillList(params) {
  const list = await api.fetchSkills('', true)
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
    title: '技能名称',
    key: 'name',
    minWidth: 140,
    ellipsis: { tooltip: true },
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
              default: () => '确定删除该技能吗？',
            },
        ),
      ]
    },
  },
])
</script>

<template>
  <CommonPage show-footer title="Skills 管理">
    <NAlert type="info" :bordered="false" class="manage-tip">
      管理可在聊天中选择的 Agent 技能。仅「启用」状态的技能会出现在聊天页选择器中；config 为 JSON，可存放提示词、参数等扩展配置。
    </NAlert>
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :query-bar-props="queryBarProps"
        :is-pagination="true"
        :remote="false"
        :scroll-x="900"
        :columns="columns"
        :get-data="fetchSkillList"
        row-key="id"
        @query-bar-create="handleAdd"
    >
      <template #queryBar>
        <QueryBarItem label="技能名称：">
          <NInput
              v-model:value="queryItems.name"
              clearable
              placeholder="请输入技能名称或描述"
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
            label="技能名称"
            path="name"
            :rule="{ required: true, message: '请输入技能名称', trigger: ['input', 'blur'] }"
        >
          <NInput v-model:value="modalForm.name" placeholder="如：代码审查" />
        </NFormItem>
        <NFormItem label="技能描述" path="description">
          <NInput
              v-model:value="modalForm.description"
              type="textarea"
              :rows="2"
              placeholder="可选，描述技能用途"
          />
        </NFormItem>
        <NFormItem label="是否启用" path="is_enabled">
          <NSwitch v-model:value="modalForm.is_enabled" />
        </NFormItem>
        <NFormItem
            label="配置 JSON"
            path="config_text"
            :rule="{ validator: validateConfig, trigger: ['input', 'blur'] }"
        >
          <NInput
              v-model:value="modalForm.config_text"
              type="textarea"
              :rows="8"
              placeholder='可选，如：{ "prompt": "你是代码审查助手..." }'
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
</style>
