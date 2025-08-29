#redis:
#	docker run -p 6379:6379 -p 8001:8001 redis/redis-stack
web:
	flask run --debug
redis:
	docker-compose up
