import { createContext, useContext } from 'react'

export const ChartRemeasureContext = createContext<string | number>(0)

export function useChartRemeasureKey() {
  return useContext(ChartRemeasureContext)
}
