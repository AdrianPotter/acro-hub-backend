# ── Moves Table ───────────────────────────────────────────────────────────────

resource "aws_dynamodb_table" "moves" {
  name         = "${var.app_name}-moves-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "moveId"

  attribute {
    name = "moveId"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${var.app_name}-moves-${var.environment}"
  }
}

# ── Move Edges Table ──────────────────────────────────────────────────────────
#
# Stores directed edges between moves for the global prerequisite DAG.
# hash_key  : fromMoveId  — the prerequisite move
# range_key : toMoveId    — the move that requires the prerequisite
#
# GSI "toMoveId-fromMoveId-index" enables efficient prerequisite lookups:
# given a move, find all edges whose destination is that move (its prerequisites).

resource "aws_dynamodb_table" "move_edges" {
  name         = "${var.app_name}-move-edges-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "fromMoveId"
  range_key    = "toMoveId"

  attribute {
    name = "fromMoveId"
    type = "S"
  }

  attribute {
    name = "toMoveId"
    type = "S"
  }

  global_secondary_index {
    name            = "toMoveId-fromMoveId-index"
    hash_key        = "toMoveId"
    range_key       = "fromMoveId"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${var.app_name}-move-edges-${var.environment}"
  }
}

# ── Events Table ──────────────────────────────────────────────────────────────

resource "aws_dynamodb_table" "events" {
  name         = "${var.app_name}-events-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "eventId"
  range_key    = "timestamp"

  attribute {
    name = "eventId"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  attribute {
    name = "userId"
    type = "S"
  }

  attribute {
    name = "eventType"
    type = "S"
  }

  global_secondary_index {
    name            = "userId-timestamp-index"
    hash_key        = "userId"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "eventType-timestamp-index"
    hash_key        = "eventType"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${var.app_name}-events-${var.environment}"
  }
}
