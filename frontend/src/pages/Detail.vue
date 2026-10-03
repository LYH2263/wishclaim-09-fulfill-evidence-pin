<template>
  <div class="wall">
    <h1 class="serif">{{ w.title }}</h1>
    <p>{{ w.note }}</p>
    <p class="tag">状态 {{ w.status }} · 认领人 {{ w.claimer || '—' }}</p>
    <p v-if="err" class="err">{{ err }}</p>

    <div v-if="w.status !== 'fulfilled'">
      <input v-model="claimer" placeholder="你的名字" />
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button @click="claim">认领锁定</button>
        <button class="ghost" @click="release">释放</button>
      </div>
    </div>

    <!-- claimed：举证包预览（不改 status）+ 完整举证提交 -->
    <section v-if="w.status === 'claimed'" class="proof-box">
      <h3 class="serif">核销举证包 · 预览</h3>
      <p class="tag">{{ pv.summary }}</p>
      <label>渠道（枚举）</label>
      <select v-model="form.channel">
        <option value="" disabled>请选择核销渠道</option>
        <option v-for="ch in pv.channels" :key="ch.value" :value="ch.value">{{ ch.icon }} {{ ch.label }}</option>
      </select>
      <input v-model="form.ref" placeholder="凭证号（如快递单号 / 签收编号）" />
      <textarea v-model="form.note" rows="3" placeholder="举证说明（交付经过 / 确认情况）"></textarea>
      <button @click="fulfill">提交完整举证并核销</button>
    </section>

    <!-- fulfilled：冻结举证区，禁止再改 -->
    <section v-else-if="w.status === 'fulfilled'" class="proof-box frozen">
      <h3 class="serif">举证快照 · 已冻结</h3>
      <div v-if="w.proof">
        <p class="proof-line">{{ w.proof.channel_icon }} {{ w.proof.channel_label }} · 凭证 {{ w.proof.ref }}</p>
        <p>{{ w.proof.note }}</p>
        <p class="tag">核销人 {{ w.proof.claimer || '—' }} · {{ w.proof.fulfilled_at }}</p>
      </div>
    </section>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
const props = defineProps({ id: String })
const w = ref({})
const pv = ref({ channels: [], summary: '' })
const claimer = ref('访客')
const form = ref({ channel: '', ref: '', note: '' })
const err = ref('')

async function load() {
  w.value = await api('/wishes/' + props.id)
  if (w.value.status === 'claimed') {
    pv.value = await api('/wishes/' + props.id + '/proof-preview')
  }
}
async function claim() {
  err.value = ''
  try {
    await api('/wishes/' + props.id + '/claim', { method: 'POST', body: JSON.stringify({ claimer: claimer.value }) })
    await load()
  } catch (e) { err.value = e.message }
}
async function release() {
  err.value = ''
  try {
    await api('/wishes/' + props.id + '/release', { method: 'POST', body: '{}' })
    await load()
  } catch (e) { err.value = e.message }
}
async function fulfill() {
  err.value = ''
  if (!form.value.channel || !form.value.ref.trim() || !form.value.note.trim()) {
    err.value = '举证不完整：渠道、凭证号、说明均为必填'
    return
  }
  try {
    await api('/wishes/' + props.id + '/fulfill', { method: 'POST', body: JSON.stringify(form.value) })
    await load()
  } catch (e) { err.value = e.message }
}
onMounted(load)
</script>
