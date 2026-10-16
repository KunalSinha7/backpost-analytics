import {
  type ColumnDef,
  createPaginatedRowModel,
  createSortedRowModel,
  flexRender,
  type RowData,
  rowPaginationFeature,
  rowSortingFeature,
  type SortingState,
  sortFn_alphanumeric,
  sortFn_datetime,
  sortFn_text,
  tableFeatures,
  useTable,
} from "@tanstack/react-table"
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

interface ServerPaginationProps {
  totalCount: number
  page: number
  pageSize: number
  onPageChange: (page: number) => void
  onPageSizeChange: (size: number) => void
}

// v9 only registers what we list; these sortFns are the ones the default
// `sortFn: "auto"` resolves to, matching v8's bundled behavior.
const dataTableFeatures = tableFeatures({
  rowPaginationFeature,
  rowSortingFeature,
  paginatedRowModel: createPaginatedRowModel(),
  sortedRowModel: createSortedRowModel(),
  sortFns: {
    alphanumeric: sortFn_alphanumeric,
    datetime: sortFn_datetime,
    text: sortFn_text,
  },
})

export type DataTableFeatures = typeof dataTableFeatures

interface DataTableProps<TData extends RowData> {
  columns: ColumnDef<DataTableFeatures, TData>[]
  data: TData[]
  pageSize?: number
  enableSorting?: boolean
  serverPagination?: ServerPaginationProps
  onRowClick?: (row: TData) => void
}

export function DataTable<TData extends RowData>({
  columns,
  data,
  pageSize,
  enableSorting = true,
  serverPagination,
  onRowClick,
}: DataTableProps<TData>) {
  const [sorting, setSorting] = useState<SortingState>([])

  const table = useTable({
    features: dataTableFeatures,
    data,
    columns,
    onSortingChange: setSorting,
    enableSorting,
    ...(serverPagination
      ? {
          manualPagination: true,
          pageCount: Math.ceil(
            serverPagination.totalCount / serverPagination.pageSize,
          ),
          state: {
            sorting,
            pagination: {
              pageIndex: serverPagination.page,
              pageSize: serverPagination.pageSize,
            },
          },
        }
      : {
          state: { sorting },
          initialState: {
            pagination: { pageIndex: 0, pageSize: pageSize ?? 10 },
          },
        }),
  })

  const serverPageCount = serverPagination
    ? Math.ceil(serverPagination.totalCount / serverPagination.pageSize)
    : 0
  const showPagination = serverPagination
    ? serverPagination.totalCount > serverPagination.pageSize
    : table.getPageCount() > 1

  const startEntry = serverPagination
    ? serverPagination.page * serverPagination.pageSize + 1
    : table.state.pagination.pageIndex * table.state.pagination.pageSize + 1
  const endEntry = serverPagination
    ? Math.min(
        (serverPagination.page + 1) * serverPagination.pageSize,
        serverPagination.totalCount,
      )
    : Math.min(
        (table.state.pagination.pageIndex + 1) *
          table.state.pagination.pageSize,
        data.length,
      )
  const totalEntries = serverPagination
    ? serverPagination.totalCount
    : data.length
  const currentPage = serverPagination
    ? serverPagination.page + 1
    : table.state.pagination.pageIndex + 1
  const totalPages = serverPagination ? serverPageCount : table.getPageCount()
  const currentPageSize = serverPagination
    ? serverPagination.pageSize
    : table.state.pagination.pageSize

  const canPreviousPage = serverPagination
    ? serverPagination.page > 0
    : table.getCanPreviousPage()
  const canNextPage = serverPagination
    ? serverPagination.page < serverPageCount - 1
    : table.getCanNextPage()

  const goToFirstPage = () => {
    if (serverPagination) {
      serverPagination.onPageChange(0)
    } else {
      table.setPageIndex(0)
    }
  }
  const goToPreviousPage = () => {
    if (serverPagination) {
      serverPagination.onPageChange(serverPagination.page - 1)
    } else {
      table.previousPage()
    }
  }
  const goToNextPage = () => {
    if (serverPagination) {
      serverPagination.onPageChange(serverPagination.page + 1)
    } else {
      table.nextPage()
    }
  }
  const goToLastPage = () => {
    if (serverPagination) {
      serverPagination.onPageChange(serverPageCount - 1)
    } else {
      table.setPageIndex(table.getPageCount() - 1)
    }
  }
  const handlePageSizeChange = (value: string) => {
    if (serverPagination) {
      serverPagination.onPageSizeChange(Number(value))
      serverPagination.onPageChange(0)
    } else {
      table.setPageSize(Number(value))
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id} className="hover:bg-transparent">
              {headerGroup.headers.map((header) => {
                return (
                  <TableHead key={header.id}>
                    {header.isPlaceholder ? null : header.column.getCanSort() ? (
                      <button
                        type="button"
                        className="flex items-center gap-1 hover:text-foreground"
                        onClick={() => header.column.toggleSorting()}
                      >
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                        {header.column.getIsSorted() === "asc" ? (
                          <ArrowUp className="h-3.5 w-3.5" />
                        ) : header.column.getIsSorted() === "desc" ? (
                          <ArrowDown className="h-3.5 w-3.5" />
                        ) : (
                          <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground" />
                        )}
                      </button>
                    ) : (
                      flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )
                    )}
                  </TableHead>
                )
              })}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.length ? (
            table.getRowModel().rows.map((row) => (
              <TableRow
                key={row.id}
                onClick={
                  onRowClick ? () => onRowClick(row.original) : undefined
                }
                className={onRowClick ? "cursor-pointer" : undefined}
              >
                {row.getAllCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : (
            <TableRow className="hover:bg-transparent">
              <TableCell
                colSpan={columns.length}
                className="h-32 text-center text-muted-foreground"
              >
                No results found.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {showPagination && (
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 border-t bg-muted/20">
          <div className="flex flex-col sm:flex-row sm:items-center gap-4">
            <div className="text-sm text-muted-foreground">
              Showing {startEntry} to {endEntry} of{" "}
              <span className="font-medium text-foreground">
                {totalEntries}
              </span>{" "}
              entries
            </div>
            <div className="flex items-center gap-x-2">
              <p className="text-sm text-muted-foreground">Rows per page</p>
              <Select
                value={`${currentPageSize}`}
                onValueChange={handlePageSizeChange}
              >
                <SelectTrigger className="h-8 w-[70px]">
                  <SelectValue placeholder={currentPageSize} />
                </SelectTrigger>
                <SelectContent side="top">
                  {[5, 10, 25, 50].map((size) => (
                    <SelectItem key={size} value={`${size}`}>
                      {size}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex items-center gap-x-6">
            <div className="flex items-center gap-x-1 text-sm text-muted-foreground">
              <span>Page</span>
              <span className="font-medium text-foreground">{currentPage}</span>
              <span>of</span>
              <span className="font-medium text-foreground">{totalPages}</span>
            </div>

            <div className="flex items-center gap-x-1">
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={goToFirstPage}
                disabled={!canPreviousPage}
              >
                <span className="sr-only">Go to first page</span>
                <ChevronsLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={goToPreviousPage}
                disabled={!canPreviousPage}
              >
                <span className="sr-only">Go to previous page</span>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={goToNextPage}
                disabled={!canNextPage}
              >
                <span className="sr-only">Go to next page</span>
                <ChevronRight className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={goToLastPage}
                disabled={!canNextPage}
              >
                <span className="sr-only">Go to last page</span>
                <ChevronsRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
