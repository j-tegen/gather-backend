import graphene

class ParticipantStatus(graphene.Enum):
    INTERESTED = "INTERESTED"
    GOING = "GOING"
    NOTGOING = "NOTGOING"
    INVITED = "INVITED"


class Gender(graphene.Enum):
    NOANSWER = ""
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class FriendStatus(graphene.Enum):
    PENDING = "PENDING"
    FRIENDS = "FRIENDS"
    BLOCKED = "BLOCKED"