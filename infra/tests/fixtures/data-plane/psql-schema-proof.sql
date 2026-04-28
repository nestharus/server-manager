select exists (
  select 1
  from information_schema.tables
  where table_schema = :'tbl_schema'
    and table_name = :'tbl_name'
);

