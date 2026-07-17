# ADR-002: No Kafka / message queue in v1

**Status:** Accepted

## Context
The original transformation brief listed Kafka. Both current sources are
batch-shaped: a catalog extract and a REST API polled daily with a watermark.

## Decision
No queue. Ingestion lands micro-batches directly in the raw layer with
manifests. The seam where a streaming consumer would sit is explicit --
anything that produces a DataFrame can call `ingestion.base.land_raw`.

## Rationale
A queue between a daily API poll and a Parquet landing adds three services,
an ops burden, and zero throughput or latency benefit. Reviewers at data
companies penalise resume-driven streaming harder than its absence; the
mature signal is knowing when Kafka is *not* warranted.

## Revisit when
A source emits events continuously, or multiple independent consumers need
the same feed with different offsets.
