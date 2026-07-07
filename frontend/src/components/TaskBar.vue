<template>
  <footer class="taskbar">
    <span class="taskbar-label">后台任务</span>
    <div class="taskbar-actions">
      <el-button size="small" @click="trigger('collect')" :loading="loading === 'collect'">
        采集数据
      </el-button>
      <el-button size="small" @click="trigger('clean')" :loading="loading === 'clean'">
        清洗数据
      </el-button>
      <el-button size="small" @click="trigger('extract')" :loading="loading === 'extract'">
        信息抽取
      </el-button>
      <el-button size="small" @click="trigger('align')" :loading="loading === 'align'">
        实体对齐
      </el-button>
      <el-button size="small" @click="trigger('discover')" :loading="loading === 'discover'">
        新岗位发现
      </el-button>
      <el-button size="small" type="primary" @click="trigger('report')" :loading="loading === 'report'">
        导出报告
      </el-button>
    </div>
    <span class="taskbar-hint">（功能待实现）</span>
  </footer>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const loading = ref(null)

function trigger(task) {
  loading.value = task
  setTimeout(() => {
    loading.value = null
    ElMessage.info(`后台任务 [${task}] 已提交（功能待实现）`)
  }, 800)
}
</script>

<style scoped>
.taskbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,.06);
  margin-top: 20px;
  flex-wrap: wrap;
}
.taskbar-label {
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  white-space: nowrap;
}
.taskbar-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.taskbar-hint {
  font-size: 12px;
  color: #94a3b8;
  margin-left: auto;
}
</style>
