# Database deployment for staging.
variable "db_endpoint" {
  type        = string
  description = "RDS endpoint to apply schema migrations against"
}

variable "migration_file" {
  type        = string
  default     = "../migrations/001_add_user_email.sql"
}

resource "null_resource" "apply_migration" {
  provisioner "local-exec" {
    command = "psql -h ${var.db_endpoint} -f ${var.migration_file}"
  }
  triggers = {
    migration = filemd5(var.migration_file)
  }
}
