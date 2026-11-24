<template>
  <div class="gi_page workplace">
    <header class="workspace-header">
      <div>
        <h1>工程实训工作台</h1>
        <p>{{ userStore.nickname }} · 个人资料空间</p>
      </div>
      <a-button @click="router.push('/user/profile')">个人中心</a-button>
    </header>
    <WorkspaceKnowledge :key="userStore.userInfo.id" />
  </div>
</template>

<script setup lang="ts">
import WorkspaceKnowledge from './components/WorkspaceKnowledge.vue'
import { useUserStore } from '@/stores'

defineOptions({ name: 'Workplace' })
const userStore = useUserStore()
const router = useRouter()
</script>

<style scoped lang="scss">
.workplace {
  color: var(--color-text-1);
}

.workspace-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 22px 24px;
  margin-bottom: 16px;
  background: var(--color-bg-2);
  border-left: 4px solid rgb(var(--primary-6));
  border-radius: 4px;

  h1 { margin: 0; font-size: 22px; }
  p { margin: 6px 0 0; color: var(--color-text-3); }
}
</style>
