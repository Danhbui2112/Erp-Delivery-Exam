# ERP Platform Delivery Management

Odoo 19 Community addons for ERP implementation delivery projects.

## Addons

- `erp_delivery_core`: customer metadata, project/task delivery fields, ERP solution catalog, access rules, and Go-live validation.
- `erp_delivery_sale`: creates a delivery project and solution-module rows from a confirmed sales order. Depends on Core, not Quality Gate.
- `erp_delivery_quality_gate`: optional project score/threshold check. Depends on Core, not Sales.

## Install

Add the Odoo 19 and custom addon paths, then install the desired modules:

```bash
./odoo19/odoo-bin \
  --addons-path=odoo19/addons,custom_addons \
  -d erp_delivery_dev \
  -i erp_delivery_core,erp_delivery_sale,erp_delivery_quality_gate
```

The Sales and Quality Gate addons can also be installed separately with Core. The ERP Delivery app opens the project list; open a project to use its ERP Delivery and optional Quality Gate tabs.

## Performance Design

1. Project module totals, mandatory-task progress, health risks, and sales-order project counts use `_read_group` over whole recordsets. This avoids one query per project. Aggregates are stored for fast list reads, at the cost of recomputation when source rows change.
2. Project creation uses `@api.model_create_multi`, and the batch performance test creates 50 projects and 500 tasks together. Batch calls reduce ORM overhead, while large batches still need bounded sizes to control transaction memory and lock duration.
3. Search-oriented fields such as project code, delivery state, expected Go-live date, customer code, risk, health, and acceptance have indexes. Indexes improve selective filtering but add write/storage cost; verify low-cardinality filters against representative query plans before adding more.
4. Stored health status is refreshed daily in batches of 500 because overdue status can change when the date advances without a project write. The batch approach bounds memory, while status may be stale until the scheduled job runs.

## Tests

Run the Core and Sales suites:

```bash
./odoo19/odoo-bin \
  --addons-path=odoo19/addons,custom_addons \
  -d erp_delivery_test \
  -i erp_delivery_core,erp_delivery_sale \
  --test-enable \
  --test-tags=/erp_delivery_core,/erp_delivery_sale \
  --stop-after-init
```

Add `erp_delivery_quality_gate` to `-i` and `--test-tags` to run the combined integration suite.