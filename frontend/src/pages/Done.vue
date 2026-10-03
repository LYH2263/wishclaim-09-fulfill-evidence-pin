<template>
  <div class="wall">
    <h1 class="serif">已完成</h1>
    <p class="tag">仅展示已核销（fulfilled）的愿望</p>
    <article v-for="w in rows" :key="w.id" class="card" @click="$router.push('/wishes/'+w.id)">
      <h3>{{ w.title }}</h3>
      <p>{{ w.claimer }}</p>
      <p v-if="w.proof_card" class="proof-line">{{ w.proof_card.summary }}</p>
    </article>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
const rows = ref([])
onMounted(async () => { rows.value = await api('/done') })
</script>
