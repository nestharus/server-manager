create table if not exists init113_workload_probe (
    id integer primary key,
    marker text not null
);

insert into init113_workload_probe (id, marker)
values (1, 'init-113-application-workloads')
on conflict (id) do update set marker = excluded.marker;
