#!/usr/bin/env python3

# Class for Voters
class Voter:
	def __init__(self, ID, balance, malicious):
		self.ID = ID
		self.balance = balance
		self.malicious = malicious