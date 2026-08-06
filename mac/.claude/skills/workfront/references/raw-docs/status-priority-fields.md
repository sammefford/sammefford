# Workfront Status Codes

Source: `mcp__workfront-hub__workflow_read_workflow_docs` — `workfront://reference/status-codes`

## Project Statuses

| Code  | Name      | Description                        |
| ----- | --------- | ---------------------------------- |
| `CUR` | Current   | Active, in progress                |
| `PLN` | Planning  | Not yet started, in planning phase |
| `CPL` | Complete  | Finished                           |
| `DED` | Dead      | Cancelled/abandoned                |
| `ONH` | On Hold   | Paused                             |
| `REQ` | Requested | Submitted for approval             |
| `APR` | Approved  | Approved but not yet started       |
| `REJ` | Rejected  | Request rejected                   |
| `IDA` | Idea      | Early stage concept                |

## Task Statuses

| Code  | Name        | Description                      |
| ----- | ----------- | --------------------------------- |
| `NEW` | New         | Not yet started                  |
| `INP` | In Progress | Work underway                    |
| `CPL` | Complete    | Finished (percentComplete = 100) |

## Issue (OpTask) Statuses

| Code  | Name          | Description               |
| ----- | ------------- | -------------------------- |
| `NEW` | New           | Newly created              |
| `INP` | In Progress   | Being worked on            |
| `AWA` | Awaiting      | Waiting for input          |
| `ONH` | On Hold       | Paused                     |
| `CPL` | Complete      | Resolved                   |
| `CLS` | Closed        | Closed after resolution    |
| `WNR` | Won't Resolve | Closed without resolution  |

## Project Condition Codes

| Code | Name       | Description                |
| ---- | ---------- | --------------------------- |
| `OT` | On Target  | On track                   |
| `AR` | At Risk    | May miss deadlines         |
| `IT` | In Trouble | Will likely miss deadlines |

## Priority Values

| Value | Level  |
| ----- | ------ |
| `0`   | None   |
| `1`   | Low    |
| `2`   | Normal |
| `3`   | High   |
| `4`   | Urgent |

## Issue Severity Values

| Value | Level                  |
| ----- | ---------------------- |
| `1`   | Cosmetic               |
| `2`   | Causes Confusion       |
| `3`   | Bug with workaround    |
| `4`   | Bug with no workaround |
| `5`   | Fatal error            |

## Issue Types (opTaskType)

| Code  | Type           |
| ----- | -------------- |
| `BUG` | Bug Report     |
| `RQS` | Request        |
| `ISS` | Issue          |
| `CRQ` | Change Request |
