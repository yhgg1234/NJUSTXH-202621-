<template>
  <div ref="rootElement" class="search-select">
    <button
      class="select-trigger"
      type="button"
      :disabled="disabled"
      :aria-label="ariaLabel"
      :aria-expanded="open"
      @click="toggleDropdown"
    >
      <span :class="{ placeholder: !selectedOption }">
        {{ selectedOption?.label || placeholder }}
      </span>
      <span class="chevron" aria-hidden="true">⌄</span>
    </button>

    <div v-if="open" class="select-dropdown">
      <input
        ref="searchInput"
        v-model.trim="query"
        class="search-input"
        :placeholder="searchPlaceholder"
        @keydown.esc="closeDropdown"
      />
      <div class="option-list">
        <button class="select-option clear-option" type="button" @click="selectValue('')">
          {{ emptyLabel }}
        </button>
        <button
          v-for="option in filteredOptions"
          :key="option.value"
          class="select-option"
          :class="{ active: option.value === modelValue }"
          type="button"
          @click="selectValue(option.value)"
        >
          <span>{{ option.label }}</span>
          <small v-if="option.value !== option.label">{{ option.value }}</small>
        </button>
        <p v-if="filteredOptions.length === 0" class="empty-options">没有匹配选项</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: '请选择' },
  searchPlaceholder: { type: String, default: '输入关键词搜索' },
  emptyLabel: { type: String, default: '全部' },
  ariaLabel: { type: String, default: '搜索选择' },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const rootElement = ref(null)
const searchInput = ref(null)
const open = ref(false)
const query = ref('')

const selectedOption = computed(() => (
  props.options.find((option) => option.value === props.modelValue)
))
const filteredOptions = computed(() => {
  const keyword = query.value.toLocaleLowerCase()
  if (!keyword) return props.options
  return props.options.filter((option) => (
    `${option.label} ${option.value}`.toLocaleLowerCase().includes(keyword)
  ))
})

async function toggleDropdown() {
  open.value = !open.value
  query.value = ''
  if (open.value) {
    await nextTick()
    searchInput.value?.focus()
  }
}

function closeDropdown() {
  open.value = false
  query.value = ''
}

function selectValue(value) {
  emit('update:modelValue', value)
  closeDropdown()
}

function handleOutsideClick(event) {
  if (!rootElement.value?.contains(event.target)) closeDropdown()
}

onMounted(() => document.addEventListener('pointerdown', handleOutsideClick))
onBeforeUnmount(() => document.removeEventListener('pointerdown', handleOutsideClick))
</script>

<style scoped>
.search-select { position: relative; min-width: 0; }
.select-trigger { display: flex; align-items: center; justify-content: space-between; width: 100%; height: 40px; padding: 0 11px; border: 1px solid #cbd5e1; border-radius: 8px; color: #0f172a; background: #fff; font: inherit; font-weight: 400; text-align: left; }
.select-trigger:hover, .select-trigger[aria-expanded="true"] { border-color: #2563eb; }
.select-trigger[aria-expanded="true"] { box-shadow: 0 0 0 3px rgba(37, 99, 235, .12); }
.select-trigger:disabled { cursor: wait; color: #94a3b8; background: #f8fafc; }
.placeholder { color: #94a3b8; }
.chevron { margin-left: 8px; color: #64748b; font-size: 17px; }
.select-dropdown { position: absolute; z-index: 20; top: calc(100% + 6px); left: 0; width: max(100%, 280px); padding: 8px; border: 1px solid #dbe3ef; border-radius: 10px; background: #fff; box-shadow: 0 16px 36px rgba(15, 23, 42, .16); }
.search-input { box-sizing: border-box; width: 100%; padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 7px; outline: none; font: inherit; }
.search-input:focus { border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37, 99, 235, .1); }
.option-list { max-height: 260px; margin-top: 7px; overflow-y: auto; }
.select-option { display: flex; flex-direction: column; gap: 2px; width: 100%; padding: 8px 9px; border: 0; border-radius: 7px; color: #1e293b; background: transparent; font: inherit; font-weight: 500; text-align: left; }
.select-option:hover, .select-option.active { color: #1d4ed8; background: #eff6ff; }
.select-option small { color: #94a3b8; font: 11px ui-monospace, monospace; }
.clear-option { color: #64748b; border-bottom: 1px solid #eef2f7; border-radius: 0; }
.empty-options { margin: 14px 8px; color: #94a3b8; font-size: 13px; text-align: center; }
</style>
