import { createQuery } from "@tanstack/solid-query";
import { createSolidTable, flexRender, getCoreRowModel } from "@tanstack/solid-table";
import { createVirtualizer } from "@tanstack/solid-virtual";
import { createMemo, For, Show } from "solid-js";

import { fetchAdminChapters, fetchCurrentPrincipal, type AdminChapterSummary } from "@/api/client";
import { Icon } from "@/components/icons/Icon";
import { Button } from "@/components/primitives/Button";

import styles from "./admin.module.css";

const columns = [
  {
    header: "Chapter",
    accessorKey: "name",
  },
  {
    header: "State",
    accessorKey: "state",
  },
  {
    header: "Version",
    accessorKey: "version",
  },
  {
    header: "Created",
    accessorKey: "created_at",
    cell: (info: { getValue: () => string }) => new Date(info.getValue()).toLocaleDateString(),
  },
];

export function AdminChaptersRoute() {
  let scrollRef: HTMLDivElement | undefined;
  const principal = createQuery(() => ({
    queryKey: ["me"],
    queryFn: fetchCurrentPrincipal,
  }));
  const chapters = createQuery(() => ({
    queryKey: ["admin", "chapters"],
    queryFn: fetchAdminChapters,
  }));
  const data = createMemo<AdminChapterSummary[]>(() => chapters.data ?? []);
  const table = createMemo(() =>
    createSolidTable({
      get data() {
        return data();
      },
      columns,
      getCoreRowModel: getCoreRowModel(),
    }),
  );
  const rows = createMemo(() => table().getRowModel().rows);
  const virtualizer = createVirtualizer({
    count: rows().length,
    getScrollElement: () => scrollRef ?? null,
    estimateSize: () => 44,
    overscan: 6,
  });

  return (
    <section class={styles.adminPanel} aria-labelledby="admin-title">
      <div class={styles.headerRow}>
        <div>
          <p class="eyebrow">Auth-gated surface</p>
          <h2 id="admin-title">Chapter administration</h2>
          <p>
            Identity comes from Pomerium headers through the API. The SPA does not own tokens or
            OIDC state.
          </p>
        </div>
        <Button type="button" variant="secondary" onClick={() => void chapters.refetch()}>
          <Icon name="shield-check" title="Refresh" />
          Refresh
        </Button>
      </div>

      <dl class={styles.identityStrip}>
        <div>
          <dt>Principal</dt>
          <dd>{principal.data?.email ?? principal.data?.subject ?? "Loading"}</dd>
        </div>
        <div>
          <dt>Provider</dt>
          <dd>{principal.data?.provider ?? "Pomerium"}</dd>
        </div>
      </dl>

      <div ref={scrollRef} class={styles.tableScroller} data-testid="chapter-table">
        <table>
          <thead>
            <For each={table().getHeaderGroups()}>
              {(headerGroup) => (
                <tr>
                  <For each={headerGroup().headers}>
                    {(header) => (
                      <th>{flexRender(header().column.columnDef.header, header().getContext())}</th>
                    )}
                  </For>
                </tr>
              )}
            </For>
          </thead>
          <tbody style={{ height: `${virtualizer.getTotalSize()}px` }}>
            <Show
              when={!chapters.isPending && rows().length > 0}
              fallback={
                <tr>
                  <td colspan={columns.length}>
                    {chapters.isPending ? "Loading chapters" : "No chapters yet"}
                  </td>
                </tr>
              }
            >
              <For each={virtualizer.getVirtualItems()}>
                {(virtualRow) => {
                  const row = rows()[virtualRow().index];
                  return (
                    <tr style={{ transform: `translateY(${virtualRow().start}px)` }}>
                      <For each={row.getVisibleCells()}>
                        {(cell) => (
                          <td>{flexRender(cell().column.columnDef.cell, cell().getContext())}</td>
                        )}
                      </For>
                    </tr>
                  );
                }}
              </For>
            </Show>
          </tbody>
        </table>
      </div>
    </section>
  );
}
