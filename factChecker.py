#!/usr/bin/env python3
from voters import Voter
from tqdm import tqdm
import random
import secrets

# Custom exception for errors
class CustomException(Exception):
	def __init__(self, message):
		self.message = message
		super().__init__(self.message)

# Fact Checker Contract
class FactChecker:
	'''
		balance: Balance of the Smart Contract for Voting purposes
		owner: Owner of the Smart Contract
		requestor: Address of the requestor
		possibleTopics: list of possible topics
		news: Current NEWS struct which is being evaluated
		trustworthiness: mapping(  voterID ==> mapping( newsTopic ==> trustworthiness-rating ) )
		currentVoters: List of Voters for current term
		votes: Voters mapping with address (ID) ==> voting value
		running: Is a existing fact Checking process going on
		votingStake: Stake needed to deposit by voters to be allowed to vote. Initial value = 200. This done to avoid sybil attack
		newsTerm: Total number of NEWS processed till now
	'''
	def __init__(self, owner, possibleTopics, votingStake):
		self.balance = 0
		self.owner = owner
		self.requestor = None
		self.possibleTopics = possibleTopics
		self.news = None
		self.trustworthiness = dict()
		self.currentVoters = []
		self.votes = dict()
		self.running = False
		self.votingStake = votingStake
		self.newsTerm = 0


	# News class => equivalent for Solidity Struct
	class News:
		'''
		topic: Topic of the news (string)
		content: News content (string)
		fees: Fees paid by the requestor for fact checking
		'''
		def __init__(self, topic, content, fees):
			self.topic = topic
			self.content = content
			self.fees = fees

	# Get News Details for any user
	def getNewsDetails(self):
		return self.news.topic, self.news.content, self.news.fees

	# Change Voting Stake (only owner can call)
	def changeVotingStake(self, newVotingStake, requestor):
		
		if requestor != self.owner:
			raise CustomException("Only owner can call this function!!")

		self.votingStake = newVotingStake

	# Voter Registration for current Term of Fact checking
	def registerVoterCurrentTerm(self, vote, typeOfVote, fees, requestor):

		if fees < self.votingStake:
			raise CustomException("Not Enough Stake supplied!!")

		if typeOfVote != "decimal" and typeOfVote != "binary":
			raise CustomException("typeOfVote incorrect!!")

		self.balance += fees

		if typeOfVote == "decimal":
			vote = (0 if vote < 5 else 1) 

		self.votes[requestor] = vote
		self.currentVoters.append(requestor)

		# This code is not required in Solidity as it defaults unknown keys to 0
		if requestor not in self.trustworthiness:
			self.trustworthiness[requestor] = dict()
			self.trustworthiness[requestor][self.news.topic] = 0
		elif self.news.topic not in self.trustworthiness[requestor]:
			self.trustworthiness[requestor][self.news.topic] = 0

	# Function to request for fact checking
	def requestChecking(self, topic, content, fees, requestor):
		
		if self.running:
			raise CustomException("Fact Checker not free!!")

		if topic not in self.possibleTopics:
			raise CustomException("NEWS Topic not in possible Topics!!")
		
		self.balance += fees

		self.news = self.News(topic, content, fees)
		self.requestor = requestor
		self.running = True
		self.currentVoters = []
		self.votes = dict()
		self.newsTerm += 1

	# Get News Fact Checking results (only requestor can call)
	def getResults(self, requestor):
		global accounts

		if not self.running:
			raise CustomException("Fact Checker free, no news being checked!!")
		
		if self.requestor != requestor:
			raise CustomException("Only News requestor can call this function!!")

		if len(self.currentVoters) == 0:
			raise CustomException("No voter has registered!!")

		result = None		

		# Bootstrapping if newsTerm is less than 100
		if self.newsTerm < 100:
			cntZero = 0
			cntOne = 0
			# Finding Majority vote, without any influence of trustworthiness
			for voter in self.currentVoters:
				if self.votes[voter] == 0:
					cntZero += 1
				else:
					cntOne += 1

			if cntOne > cntZero:
				# Transfer the rewards to majority voters uniformly and re-evaluate the trustworthiness of voters.
				for voter in self.currentVoters:
					if self.votes[voter] == 1:
						self.trustworthiness[voter][self.news.topic] += 1
						accounts[voter].balance += (self.balance / cntOne)
					else:
						self.trustworthiness[voter][self.news.topic] = max(self.trustworthiness[voter][self.news.topic]-1,0)
				
				result = "True"
			
			elif cntOne < cntZero:
				# Transfer the rewards to majority voters uniformly
				for voter in self.currentVoters:
					if self.votes[voter] == 0:
						self.trustworthiness[voter][self.news.topic] += 1
						accounts[voter].balance += (self.balance / cntZero)
					else:
						self.trustworthiness[voter][self.news.topic] = max(self.trustworthiness[voter][self.news.topic]-1,0)
				
				result = "False"
			
			else:
				# Tie, don't increase the trustworthiness, but return money to all voters
				for voter in self.currentVoters:
					accounts[voter].balance += (self.balance / len(self.currentVoters))
				
				result = "Tie"
		
		else:
			# More trustworthy voters should be given more weight
			cntZero = 0
			cntOne = 0
			valZero = 0
			valOne = 0

			# Finding Majority vote, with influence of trustworthiness
			for voter in self.currentVoters:
				if self.votes[voter] == 0:
					valZero += self.trustworthiness[voter][self.news.topic]
					cntZero += 1
				else:
					valOne += self.trustworthiness[voter][self.news.topic]
					cntOne += 1

			if valOne > valZero:
				# Transfer the rewards to majority voters uniformly and re-evaluate the trustworthiness of voters.
				for voter in self.currentVoters:
					if self.votes[voter] == 1:
						self.trustworthiness[voter][self.news.topic] += 1
						accounts[voter].balance += (self.balance / cntOne)
					else:
						self.trustworthiness[voter][self.news.topic] = max(self.trustworthiness[voter][self.news.topic]-1,0)
				
				result = "True"
			
			elif valOne < valZero:
				# Transfer the rewards to majority voters uniformly
				for voter in self.currentVoters:
					if self.votes[voter] == 0:
						self.trustworthiness[voter][self.news.topic] += 1
						accounts[voter].balance += (self.balance / cntZero)
					else:
						self.trustworthiness[voter][self.news.topic] = max(self.trustworthiness[voter][self.news.topic]-1,0)
				
				result = "False"
			
			else:
				# Tie, don't increase the trustworthiness, but return money to all voters
				for voter in self.currentVoters:
					accounts[voter].balance += (self.balance / len(self.currentVoters))
				
				result = "Tie"
		
		self.running = False
		self.news = None
		self.requestor = None
		self.currentVoters = []
		self.votes = dict()

		return result

if __name__ == "__main__":
	# All the accounts
	accounts = dict()
	trustworthyVoters = []
	remHonestVoters = []
	maliciousVoters = []


	# N,p,q values
	N = 100
	q = 0.20
	p = 0.75

	# Let M be the number of News
	M = 1000
	news = []

	topics = ["Political", "Military", "Science", "International", "Economics"]

	# Creating News truthfulness, topic, Content and requesting fees
	for _ in range(M):
		news.append([ ( 0 if random.random() < 0.5 else 1 ), "Political" ,"NewsContent" ,random.randint(1000, 2000) ])

	# Creating malicious voters
	for _ in range(int(q*N)):
		account = Voter(secrets.token_hex(5), M*200, True)
		accounts[account.ID] = account
		maliciousVoters.append(account)
	
	# Creating trustworthy voters
	for _ in range(int((N - int(N*q))*p)):
		account = Voter(secrets.token_hex(5), M*200, False)
		accounts[account.ID] = account
		trustworthyVoters.append(account)

	# Creating remaining honest voters
	for _ in range(N - int((N - int(N*q))*p)):
		account = Voter(secrets.token_hex(5), M*200, False)
		accounts[account.ID] = account
		remHonestVoters.append(account)
	
	# Simulate
	factChecker = FactChecker(secrets.token_hex(5), topics, 200)
	results = []

	for i in tqdm(range(M)):
		
		requestor = secrets.token_hex(5)
		# Request Checking by paying fee
		factChecker.requestChecking(news[i][1], news[i][2], news[i][3], requestor)
		
		# Vote by providing stake for all the accounts (Sybil resistant)

		for account in trustworthyVoters:

			# Vote Correctly
			if random.random() < 0.9:
				
				account.balance -= 200
				factChecker.registerVoterCurrentTerm(news[i][0], "binary", 200, account.ID)

			else:
				
				account.balance -= 200
				factChecker.registerVoterCurrentTerm( (0 if news[i][0] == 1 else 1), "binary", 200, account.ID)

		for account in remHonestVoters:

			# Vote Correctly
			if random.random() < 0.7:
				
				account.balance -= 200
				factChecker.registerVoterCurrentTerm(news[i][0], "binary", 200, account.ID)

			else:
				
				account.balance -= 200
				factChecker.registerVoterCurrentTerm( (0 if news[i][0] == 1 else 1), "binary", 200, account.ID)

		for account in maliciousVoters:
			# Always vote incorrectly
			account.balance -= 200
			factChecker.registerVoterCurrentTerm( (0 if news[i][0] == 1 else 1), "binary", 200, account.ID)


		# Get Results for the voting
		finalResults = factChecker.getResults(requestor)
		trustworthiness = dict()
		for voterID in factChecker.trustworthiness:
			trustworthiness[voterID] = factChecker.trustworthiness[voterID][news[i][1]] / (i+1)

		results.append([finalResults, trustworthiness])


	# Final results
	print("Final Results")
	print("Is matching?? :", results[-1][0] == ( "True" if news[-1][0] else "False") )

	tot = 0.0

	for account in trustworthyVoters:
		tot += results[-1][1][account.ID]

	print("For Very trustworthy voters, trustworthiness =", tot / len(trustworthyVoters))

	tot = 0.0

	for account in remHonestVoters:
		tot += results[-1][1][account.ID]

	print("For remaining honest voters, trustworthiness =", tot / len(remHonestVoters))

	tot = 0.0

	for account in maliciousVoters:
		tot += results[-1][1][account.ID]

	print("For Malicious Voters, trustworthiness =", tot / len(maliciousVoters))
