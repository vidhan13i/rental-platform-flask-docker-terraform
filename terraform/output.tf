output "instance_public_ip" {
  description = "Elastic IP of your server"
  value       = aws_eip.rental_eip.public_ip
}

output "ssh_command" {
  description = "Command to SSH into the server"
  value       = "ssh -i ~/.ssh/id_rsa ubuntu@${aws_eip.rental_eip.public_ip}"
}

output "api_gateway_url" {
  description = "API Gateway endpoint"
  value       = "http://${aws_eip.rental_eip.public_ip}:8000"
}

output "frontend_url" {
  description = "Frontend URL"
  value       = "http://${aws_eip.rental_eip.public_ip}"
}