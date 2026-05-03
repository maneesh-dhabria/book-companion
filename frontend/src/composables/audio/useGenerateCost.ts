export interface GenerateCostInput {
  totalUnits: number
}

export interface GenerateCost {
  minutes: number
  megabytes: number
}

export function estimateGenerateCost(input: GenerateCostInput): GenerateCost {
  const n = Math.max(0, input.totalUnits)
  return { minutes: n * 0.2, megabytes: n * 3.0 }
}
