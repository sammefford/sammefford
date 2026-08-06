# Workfront API Query Syntax — Filter Modifiers and Date Ranges

Source: `mcp__workfront-hub__workflow_read_workflow_docs` — `workfront://reference/query-syntax`
(this raw doc also covers pagination and related-field queries, kept here since they came
from the same fetched doc; `order-by.md` extracts the sorting section separately for clarity)

## Filter Modifiers (\_Mod)

Append `_Mod` to any field name to specify comparison logic. Default is `eq` (equals).

| Modifier      | SQL Equivalent                       | Example                                                                                      |
| ------------- | ------------------------------------- | ---------------------------------------------------------------------------------------------|
| `eq`          | `field = value`                       | `{ "status": "CUR" }`                                                                         |
| `ne`          | `field <> value OR field IS NULL`     | `{ "status": "DED", "status_Mod": "ne" }`                                                      |
| `gt`          | `field > value`                       | `{ "percentComplete": "50", "percentComplete_Mod": "gt" }`                                    |
| `gte`         | `field >= value`                      | `{ "plannedStartDate": "2024-01-01", "plannedStartDate_Mod": "gte" }`                         |
| `lt`          | `field < value`                       | `{ "priority": "2", "priority_Mod": "lt" }`                                                    |
| `lte`         | `field <= value`                      | `{ "plannedCompletionDate": "$$TODAY", "plannedCompletionDate_Mod": "lte" }`                  |
| `contains`    | `field LIKE '%value%'`                | `{ "name": "Campaign", "name_Mod": "contains" }`                                               |
| `cicontains`  | `UPPER(field) LIKE UPPER('%value%')`  | `{ "name": "campaign", "name_Mod": "cicontains" }`                                             |
| `notcontains` | `field NOT LIKE '%value%'`            | `{ "name": "test", "name_Mod": "notcontains" }`                                                |
| `startswith`  | `UPPER(field) LIKE UPPER('value%')`   | `{ "name": "Project", "name_Mod": "startswith" }`                                              |
| `in`          | `field IN (v1, v2, ...)`              | `{ "status": ["CUR","PLN","ONH"], "status_Mod": "in" }`                                        |
| `notin`       | `field NOT IN (v1, v2, ...)`          | `{ "status": ["DED","CAN"], "status_Mod": "notin" }`                                           |
| `between`     | `field BETWEEN v1 AND v2`             | `{ "entryDate": "2024-01-01", "entryDate_Mod": "between", "entryDate_Range": "2024-12-31" }`   |
| `isnull`      | `field IS NULL`                       | `{ "description": "", "description_Mod": "isnull" }`                                          |
| `notnull`     | `field IS NOT NULL`                   | `{ "actualCompletionDate": "", "actualCompletionDate_Mod": "notnull" }`                        |
| `isblank`     | `field IS NULL OR field = ''`         | `{ "description": "", "description_Mod": "isblank" }`                                         |
| `notblank`    | `field IS NOT NULL AND field <> ''`   | `{ "description": "", "description_Mod": "notblank" }`                                        |

### Case-Insensitive Variants

- `cieq` — case-insensitive equals
- `cine` — case-insensitive not equals
- `ciin` — case-insensitive IN
- `cinotin` — case-insensitive NOT IN
- `cicontainsany` — contains any word (space-separated)
- `cicontainsall` — contains all words (space-separated)
- `cibetween` — case-insensitive between

## Range Modifier (\_Range)

Used with `between`. Values are pipe-separated.

- **BETWEEN**: `{ "entryDate": "2024-01-01", "entryDate_Mod": "between", "entryDate_Range": "2024-12-31" }`

For `in` / `notin`, prefer passing the field value as a JSON array (see table above).

## Logical Operators

- All filters in a single object are AND'd by default
- `OR:` prefix for OR conditions: `{ "OR:a:status": "CUR", "OR:a:status_Mod": "eq", "OR:b:status": "PLN", "OR:b:status_Mod": "eq" }`
- `AND:` prefix for explicit AND grouping
- `EXISTS:` / `NOTEXISTS` for subquery conditions

## Related Field Queries

Use colon notation to filter on related objects:

- `{ "owner:name": "John", "owner:name_Mod": "cicontains" }`
- `{ "project:name": "Website", "project:name_Mod": "startswith" }`
- `{ "assignedTo:emailAddr": "john@company.com" }`

## Custom Fields

Prefix with `DE:` for data extension (custom) fields:

- `{ "DE:customField": "value" }`
- `{ "DE:department": "Marketing", "DE:department_Mod": "cicontains" }`

## Pagination

- `limit`: max results per request (default 100, max 200)
- `offset`: skip N results for pagination
