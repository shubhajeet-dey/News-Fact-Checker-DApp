// SPDX-License-Identifier: MIT
pragma solidity >=0.8.0 <0.9.0;

contract NewsFactChecker {

  struct NewsItem {
    address requestor;
    uint256 totalTrustRatingForZero; // Total trust rating of voters who voted 0
    uint256 totalTrustRatingForOne; // Total trust rating of voters who voted 1
    uint256 zeroVotes; // Total zero votes voted for the news item 
    uint256 oneVotes; // Total one votes voted for the news item
    string topic; // Topic of the newsItem belongs to
    string content; // Content of the news
    uint256 requestor_fees; // Fees provided by the requestor
    bool isProcessed; // Flag indicating if the news item is processed
    string result; // indicating if the news item is fake or not
    uint256 totalBalance; // Total money invested in this news item
    mapping(address => uint) votes; // Mapping of address to whether they have voted
    mapping(address => bool) haveVoted;
    address[] votersList; // List of addresses that have voted
  }

  mapping(bytes32 => NewsItem) public newsItems; // Mapping of keccak256 hash of news item to NewsItem
  uint256 public votingStake; // Stake required to participate in voting
  uint256 public newsTerm; // Number of news items processed (Voting Completed)
  address public owner; // Owner's address
  mapping(address => mapping(string => uint256)) trustworthiness; // Trustworthiness Rating of voters based on topic
  bool internal locked; // Lock to stop Reentrancy attack during rewards distribution

  // Events
  event Voted(address indexed voter, bytes32 indexed newsHash, uint _voteValue, string _typeOfVote);
  event FactCheckRequested(address indexed voter, bytes32 indexed newsHash, string _newsContent, string _newsTopic);
  event finalResult(bytes32 indexed newsHash, string result);

  // Constructor to initialize the DApp
    constructor(uint256 _votingStake) {
      votingStake = _votingStake;
      owner = msg.sender;
    }

  // Change voting stake for each vote (only owner can call)
    function changeVotingStake(uint256 _votingStake) external {
      require(msg.sender == owner, "Only owner can call this function!!");
      votingStake = _votingStake;
    }

  // Register as a voter for a particular news item by paying stake
    function registerVoter(bytes32 _newsHash, uint _voteValue, string calldata _typeOfVote) external payable {
        require(msg.value >= votingStake, "Not Enough Voting Stake supplied!!");
        require(((bytes(newsItems[_newsHash].topic).length != 0) && (bytes(newsItems[_newsHash].content).length != 0)), "News Item doesn't exists!!");
        require(((_voteValue >=0 && _voteValue <= 10 && keccak256(abi.encodePacked(_typeOfVote)) == keccak256(abi.encodePacked("decimal"))) || ((_voteValue == 0 || _voteValue == 1) && keccak256(abi.encodePacked(_typeOfVote)) == keccak256(abi.encodePacked("binary")))), "Vote type/value incorrect!!");
        
        uint vote = _voteValue;
        if (keccak256(abi.encodePacked(_typeOfVote)) == keccak256(abi.encodePacked("decimal"))) {
          vote = ((_voteValue >= 5)? 1 : 0);
        }
        
        // Setting the vote value and increasing the balance
        newsItems[_newsHash].totalBalance += msg.value;
        newsItems[_newsHash].votes[msg.sender] = vote;
        
        if (newsItems[_newsHash].haveVoted[msg.sender] == false) {
          newsItems[_newsHash].votersList.push(msg.sender);
          newsItems[_newsHash].haveVoted[msg.sender] = true;
        }
        emit Voted(msg.sender, _newsHash, _voteValue, _typeOfVote);
    }

    // Function for anyone to request fact-checking a news item by paying a fees
    function requestFactCheck(string calldata _newsContent, string calldata _newsTopic) external payable returns (bytes32 newsHash) {
        newsHash = keccak256(abi.encodePacked(string.concat(_newsContent, _newsTopic)));
        require(((bytes(newsItems[newsHash].topic).length == 0) && (bytes(newsItems[newsHash].content).length == 0)), "News Item already exists!!");
        require(!newsItems[newsHash].isProcessed, "News Item already processed!!");
        require(msg.value > 0, "Please pay some fees!!" );

        // Set the voting end time and participation fee for the news ite
        newsItems[newsHash].topic = _newsTopic;
        newsItems[newsHash].content = _newsContent;
        newsItems[newsHash].requestor_fees = msg.value;
        newsItems[newsHash].totalBalance += msg.value;
        newsItems[newsHash].requestor = msg.sender;
        
        emit FactCheckRequested(msg.sender, newsHash, _newsContent, _newsTopic);
    }

    // Function to process the votes and determine the trustworthiness of a news item (only requestor can call)
    function processNewsItem(bytes32 _newsHash) external returns (string memory result) {
        require(((bytes(newsItems[_newsHash].topic).length != 0) && (bytes(newsItems[_newsHash].content).length != 0)), "News Item doesn't exists!!");
        NewsItem storage news = newsItems[_newsHash];
        require(news.requestor == msg.sender, "Only News Item requestor can call this function!!");
        require(!news.isProcessed, "News item already processed!!");
        require(news.votersList.length > 0, "No voter has registered yet!!");
        require(!locked, "Re-entrancy atttack detected!!");

        uint256 _totalTrustRatingForZero; // Total trust rating of voters who voted 0
        uint256 _totalTrustRatingForOne; // Total trust rating of voters who voted 1
        uint256 _zeroVotes; // Total zero votes voted for the news item 
        uint256 _oneVotes; // Total one votes voted for the news item

        // Bootstrapping if newsTerm is less than 100
        if (newsTerm < 100) {
          
          // Finding Majority vote, without any influence of trustworthiness
          for (uint256 i=0; i<news.votersList.length; i++) {
            if (news.votes[news.votersList[i]] == 0){
                _zeroVotes++;
            }else{
                _oneVotes++;
            }
          }
          
          _totalTrustRatingForZero = _zeroVotes;
          _totalTrustRatingForOne = _oneVotes;

          // The news is true
          if(_zeroVotes < _oneVotes) {
              result = "True";
              distributeRewards(_newsHash, 1, _zeroVotes, _oneVotes);
          
          // The news is fake
          }else if(_zeroVotes > _oneVotes) {
              result = "False";
              distributeRewards(_newsHash, 0, _zeroVotes, _oneVotes);
          
          // The decision was a tie
          }else {
              result = "Tie";
              distributeRewards(_newsHash, 2, _zeroVotes, _oneVotes);
          }

        // More trustworthy voters should be given more weight
        } else {

          // Finding Majority vote, with influence of trustworthiness
          for (uint256 i=0; i<news.votersList.length; i++) {
            if (news.votes[news.votersList[i]] == 0){
                _totalTrustRatingForZero += trustworthiness[news.votersList[i]][news.topic];
                _zeroVotes++;
            }else{
                _totalTrustRatingForOne += trustworthiness[news.votersList[i]][news.topic];
                _oneVotes++;
            }
          }

          // The news is true
          if(_totalTrustRatingForZero < _totalTrustRatingForOne) {
              result = "True";
              distributeRewards(_newsHash, 1, _zeroVotes, _oneVotes);
          
          // The news is fake
          }else if(_totalTrustRatingForZero > _totalTrustRatingForOne) {
              result = "False";
              distributeRewards(_newsHash, 0, _zeroVotes, _oneVotes);
          
          // The decision was a tie
          }else {
              result = "Tie";
              distributeRewards(_newsHash, 2, _zeroVotes, _oneVotes);
          }
        }

        // Mark the news item as processed
        newsItems[_newsHash].isProcessed = true;
        newsItems[_newsHash].result = result; 
        newsItems[_newsHash].totalTrustRatingForZero = _totalTrustRatingForZero;
        newsItems[_newsHash].totalTrustRatingForOne = _totalTrustRatingForOne;
        newsItems[_newsHash].zeroVotes = _zeroVotes;
        newsItems[_newsHash].oneVotes = _oneVotes;
        newsTerm++;
        emit finalResult(_newsHash, result);
    }

    // Function to distribute rewards to voters based on the outcome of the news item (Penalize wrong voters and reward right voters)
    function distributeRewards(bytes32 _newsHash, uint _correctVote, uint256 _zeroVotes, uint256 _oneVotes) internal {
        NewsItem storage news = newsItems[_newsHash];
        
        // Reward given to a correct voter
        uint256 sharedReward;
        
        // The voting resulted in a tie
        if(_correctVote == 2) {
            // Tie, So don't increase the trustworthiness, but return total money to all voters
            sharedReward = news.totalBalance / (_zeroVotes + _oneVotes);
            for(uint256 i = 0; i < news.votersList.length; i++) {
                locked = true;
                (bool sent,) = payable(news.votersList[i]).call{value: sharedReward}("");
                // assert(sent);
                locked = false;
            }
        } else {

            // Transfer the rewards to majority voters uniformly and re-evaluate the trustworthiness of voters.
            sharedReward = news.totalBalance / ((_correctVote == 0)? _zeroVotes : _oneVotes);
            for(uint256 i = 0; i < news.votersList.length; i++) {
                if(news.votes[news.votersList[i]] == _correctVote) {
                    trustworthiness[news.votersList[i]][news.topic]++;
                    locked = true;
                    (bool sent,) = payable(news.votersList[i]).call{value: sharedReward}("");
                    // assert(sent);
                    locked = false;
                }else{
                    // uint256 trust = trustworthiness[news.votersList[i]][news.topic];
                    // trustworthiness[news.votersList[i]][news.topic] = ((trust > 0)? (trust - 1) : 0);
                    "pass";
                }
            }
        }
        
    }
}
