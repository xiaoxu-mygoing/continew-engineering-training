<template>
  <div class="workspace-body">
    <section class="workspace-column" aria-label="个人资料">
      <PrivateDocuments @documents="documents = $event" />
      <LibrarySearch :documents="documents" />
    </section>
    <aside class="workspace-column" aria-label="AI 智能问答">
      <LibraryChat :documents="documents" />
    </aside>
  </div>
</template>

<script setup lang="ts">
import LibraryChat from './LibraryChat.vue'
import LibrarySearch from './LibrarySearch.vue'
import PrivateDocuments from './PrivateDocuments.vue'
import type { TrainingDocument } from '@/apis/training/documents'

const documents = ref<TrainingDocument[]>([])
</script>

<style scoped>
.workspace-body {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.workspace-column {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
  min-width: 0;
}

@media (max-width: 1050px) {
  .workspace-body { grid-template-columns: minmax(0, 1fr); }
}
</style>
