import { useState } from "react"

const STORAGE_KEY = "table-page-size"
const DEFAULT_PAGE_SIZE = 10

export function useTablePageSize() {
  const [pageSize, setPageSizeState] = useState<number>(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored ? Number(stored) : DEFAULT_PAGE_SIZE
  })

  const setPageSize = (size: number) => {
    localStorage.setItem(STORAGE_KEY, String(size))
    setPageSizeState(size)
  }

  return [pageSize, setPageSize] as const
}
