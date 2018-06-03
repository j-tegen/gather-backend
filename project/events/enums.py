import graphene

class ParticipantStatus(graphene.Enum):
    INTERESTED = "Interested"
    GOING = "Going"
    NOTGOING = "Not going"


class Gender(graphene.Enum):
    NOANSWER = ""
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"
