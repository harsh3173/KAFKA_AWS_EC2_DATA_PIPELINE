output "ec2_public_ip" {
  description = "Public IP of the Kafka EC2 instance"
  value       = aws_instance.kafka.public_ip
}

output "ec2_public_dns" {
  description = "Public DNS of the Kafka EC2 instance"
  value       = aws_instance.kafka.public_dns
}

output "s3_bucket_arn" {
  description = "ARN of the data lake S3 bucket"
  value       = aws_s3_bucket.data_lake.arn
}

output "s3_bucket_name" {
  description = "Name of the data lake S3 bucket"
  value       = aws_s3_bucket.data_lake.id
}
