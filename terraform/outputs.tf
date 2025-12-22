output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.n8n.id
}

output "public_ip" {
  description = "Public IP address (Elastic IP)"
  value       = aws_eip.n8n.public_ip
}

output "n8n_url" {
  description = "URL to access n8n"
  value       = "https://${var.domain_name}"
}

output "ssh_command" {
  description = "SSH command to connect"
  value       = "ssh -i <your-key.pem> ec2-user@${aws_eip.n8n.public_ip}"
}

output "ssm_command" {
  description = "AWS SSM Session Manager command (no SSH key needed)"
  value       = "aws ssm start-session --target ${aws_instance.n8n.id}"
}

output "dns_record" {
  description = "DNS A record to create"
  value       = "${var.domain_name} -> ${aws_eip.n8n.public_ip}"
}
