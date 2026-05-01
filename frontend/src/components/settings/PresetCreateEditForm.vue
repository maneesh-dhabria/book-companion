<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

interface PresetPayload {
  name: string
  label: string
  description: string
  facets: Record<string, string>
}

const props = withDefaults(
  defineProps<{
    mode: 'create' | 'edit'
    facetOptions: Record<string, string[]>
    initial?: PresetPayload | null
  }>(),
  { initial: null },
)

const emit = defineEmits<{
  save: [payload: PresetPayload]
  cancel: []
}>()

const slugRe = /^[a-z][a-z0-9_]*$/

const form = reactive<PresetPayload>({
  name: props.initial?.name ?? '',
  label: props.initial?.label ?? '',
  description: props.initial?.description ?? '',
  facets: { ...(props.initial?.facets ?? {}) },
})

const submitted = ref(false)

watch(
  () => props.initial,
  (v) => {
    if (v) {
      form.name = v.name
      form.label = v.label
      form.description = v.description
      form.facets = { ...v.facets }
    }
  },
)

const nameError = computed(() => {
  if (!form.name) return 'Required'
  if (!slugRe.test(form.name)) return 'Use lowercase letters, digits, and underscores only.'
  return ''
})

const dimensions = computed(() => Object.keys(props.facetOptions))

const allFacetsSelected = computed(() =>
  dimensions.value.every((d) => !!form.facets[d]),
)

const canSave = computed(
  () => !nameError.value && form.label.trim().length > 0 && allFacetsSelected.value,
)

function selectFacet(dim: string, value: string) {
  form.facets[dim] = value
}

function onSave() {
  submitted.value = true
  if (!canSave.value) return
  emit('save', {
    name: form.name,
    label: form.label,
    description: form.description,
    facets: { ...form.facets },
  })
}
</script>

<template>
  <form class="preset-form" @submit.prevent="onSave">
    <label class="field">
      <span class="field__label">Name (slug)</span>
      <input
        name="name"
        type="text"
        v-model.trim="form.name"
        :readonly="mode === 'edit'"
        :aria-invalid="!!nameError || undefined"
      />
      <small v-if="nameError" class="field__error">{{ nameError }}</small>
    </label>

    <label class="field">
      <span class="field__label">Label</span>
      <input name="label" type="text" v-model.trim="form.label" />
    </label>

    <label class="field">
      <span class="field__label">Description</span>
      <textarea name="description" v-model="form.description" rows="2" />
    </label>

    <div v-for="dim in dimensions" :key="dim" class="field">
      <span class="field__label">{{ dim.replace('_', ' ') }}</span>
      <div class="facet-grid">
        <button
          v-for="value in facetOptions[dim]"
          :key="value"
          type="button"
          class="facet-card"
          :class="{ active: form.facets[dim] === value }"
          @click="selectFacet(dim, value)"
        >
          {{ value }}
        </button>
      </div>
    </div>

    <div class="form-actions">
      <button class="cancel" type="button" @click="emit('cancel')">Cancel</button>
      <button class="save btn-primary" type="button" :disabled="!canSave" @click="onSave">
        {{ mode === 'edit' ? 'Save changes' : 'Create preset' }}
      </button>
    </div>
  </form>
</template>

<style scoped>
.preset-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.field__label {
  font-size: 0.8em;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-text-secondary);
}
.field__error {
  color: var(--color-text-danger, #b91c1c);
  font-size: 0.85em;
}
input,
textarea {
  padding: 6px 8px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-bg-input, var(--color-bg-primary));
  color: var(--color-text-primary);
  font: inherit;
}
input[readonly] {
  opacity: 0.7;
}
.facet-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.facet-card {
  padding: 6px 12px;
  border: 1px solid var(--color-border);
  border-radius: 16px;
  background: var(--color-bg-primary);
  cursor: pointer;
  font-size: 0.9em;
}
.facet-card.active {
  background: var(--color-accent, #4f46e5);
  color: var(--color-text-on-accent, white);
  border-color: transparent;
}
.facet-card:focus-visible {
  outline: 2px solid var(--color-accent, #4f46e5);
  outline-offset: 2px;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}
.btn-primary {
  background: var(--color-accent, #4f46e5);
  color: var(--color-text-on-accent, white);
  border: none;
}
.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
button {
  padding: 6px 14px;
  border-radius: 4px;
  border: 1px solid var(--color-border);
  background: var(--color-bg-primary);
  cursor: pointer;
}
</style>
