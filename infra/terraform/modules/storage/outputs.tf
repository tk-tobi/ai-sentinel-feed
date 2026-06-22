output "raw_bucket_name" {
  value = aws_s3_bucket.raw.id
}

output "exports_bucket_name" {
  value = aws_s3_bucket.exports.id
}
