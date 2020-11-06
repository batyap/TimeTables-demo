# Has interface for the database
#-----------------
# imports
import os
from sys import stderr, exit
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, scoped_session, create_session, Session
from sqlalchemy.ext.automap import automap_base
#-------------------
# CAS Authentication cannot be run locally unfortunately
# Set this variable to 1 if local, and change to 0 before pushing
LOCAL_ENV = 0


# ALL FUNCTIONS
"""
-------------USER FUNCTIONS-----------------
add_user(firstName, lastName, netid, email=None, phone=None, preferences=None, createGroup = True)
remove_user(netid, groupid)
update_profile_info(firstName, lastName, netid, email=None, phone=None, preferences=None,createGroup = True)
get_all_users()
get_user_groups(netid)
user_exists(netid)
get_profile_info(netid)
in_group(netid)

change_user_preferences_global(netid, preferences)

get_group_preferences(groupid, netid) 
change_user_preferences_group(groupid, netid, preferences = None)
----------------------------------------------

------------GROUP FUNCTIONS-------------------

add_group(owner, groupName, shiftSchedule = None, globalshifts=None)
remove_group(groupid)
get_group_id(groupname)

// These are for the 'global' or recurring shifts week to week
get_group_shifts(groupid)
change_group_shifts(groupid, shifts = None)

// This is for the weekly schedule
get_group_schedule(groupid)
change_group_schedule(groupid, schedule)

----------------------------------------------

------------GROUP MEMBER FUNCTIONS------------
change_group_notifications(groupid, netid, emailnotif = False, textnotif = False):

get_group_notifications(netid, groupid)
get_user_schedule(netid,groupid)
update_user_schedule(netid,groupid, schedule = None)
get_user_role(netid, groupid)
"""


#temp url postgres://pheepicuurwuqg:fc272975e122789ac91401d8c19152c7ea716f2d935b3a28ad3d2e34e7131229@ec2-52-72-221-20.compute-1.amazonaws.com:5432/d7t82iju2c7ela
#----------
DATABASE_URL = os.environ['DATABASE_URL']

# create engine (db object basically)
engine = create_engine(DATABASE_URL)
#start automap and create session with automap
Base = automap_base()
Base.prepare(engine, reflect=True)

session = Session(engine)

Users = Base.classes.users
Groups = Base.classes.groups
Group_members = Base.classes.groupmembers

# call this function on the preferences array
def create_preferences(hoursList):
    output = {}
    for i in range(len(hoursList)):
        output[i] = hoursList[i]
    return output

# dict to double array
# NOTE: Append recreates the array every time to add a new item to the end. Would be better to use a set sized array instead of expanding
# especially for big arrays
def get_double_array(preferences):
    output = []
    for i in range(len(preferences)):
        output.append(preferences[str(i)])
    return output

def parse_user_schedule(netid, groupschedule):
    output = {}
    # start with blank dict
    for i in range(24):
        output[str(i)] = [False] * 7
    for key in groupschedule:
        if netid in groupschedule[key]:
            items = key.split('_')
            day = items[0]
            day = int(day)
            start = items[1]
            end = items[2]
            # make sure shift is one day
            if start < end:
                for i in range(int(start), int(end)):
                    output[str(i)][day] = True
            else:
                for i in range(int(start), 24):
                    output[str(i)][day] = True
                for i in range(int(end)):
                    output[str(i)][(day + 1) % 7] = True
    return output

# adds a user to the database
def add_user(firstName, lastName, netid, email=None, phone=None, preferences=None, createGroup = True):
    try:
        session.add(Users(firstname=firstName,lastname=lastName,netid=netid,
                    email=email,phone=phone,globalpreferences=preferences, can_create_group = createGroup))
        session.commit()
        return
    except:
        session.rollback()
        print('Add User Failed',file=stderr)
        return -1
        
# returns the netid's of all users in the db
def get_all_users():
    try: 
        ids = session.query(Users.netid).all()
        id_array = []
        for id in ids:
            id_array.append(id[0])
        return id_array
    except:
        print("unable to get all users",file=stderr)
        return -1



def user_exists(netid):
    return session.query(Users).filter(Users.netid == netid).scalar() is not None
    
# removes a user from a group
def remove_user_from_group(netid, groupid):
    try:
        userid = get_user_id(groupid,netid)
        session.execute(
            "DELETE FROM groupmembers WHERE inc=:param", {"param":userid}
        )
        # session.delete(Group_members(inc=get_user_id(groupid,netid)))
        session.flush()
        session.commit()
    except:
        session.rollback()
        print('Remove User Failed',file=stderr)
        return -1
    return

# removes user from db
def remove_user(netid):
    try:
        if in_group(netid):
            session.execute(
                "DELETE FROM groupmembers WHERE netid=:param", {"param":netid}
            )
        session.execute(
                "DELETE FROM users WHERE netid=:param", {"param":netid}
        )
        session.flush()
        session.commit()
    except:
        session.rollback()
        print('Remove User Failed',file=stderr)
        return -1
    return

#replaces the personal preferences of a user, global
def change_user_preferences_global(netid, preferences):
    try:
        session.query(Users).filter_by(netid=netid).update({Users.globalpreferences : preferences})
        session.commit()
    except:
        session.rollback()
        print('Failed to change users global preferences',file=stderr)
        return -1
    return

# this could break if we change database row names!
def get_global_preferences(netid):
    try:
        pref = session.query(Users.globalpreferences).filter_by(netid=netid).first()

        return pref._asdict()['globalpreferences']
    except:
        print('get_global_preferences() failed',file=stderr)
        return -1

# get user's group preferences, gets global preferences if no group preferences set
def get_group_preferences(groupid, netid):
    try:
        userid = get_user_id(groupid, netid)
        pref = session.query(Group_members.grouppreferences).filter_by(inc=userid).first()
        if pref == None:
            pref = session.query(Users.globalpreferences).filter_by(netid=netid).first()
            return pref._asdict()['globalpreferences']
        return pref._asdict()['grouppreferences']
    except:
        print('get_group_preferences() failed',file=stderr)
        return -1


# replaces weekly preferences of user. If none specified, 
# replaces it with global preferences
def change_user_preferences_group(groupid, netid, preferences = None):
    if(preferences==None):
       preferences = get_global_preferences(netid)
       # preferences = get_global_preferences(netid) ?
    
    userid = get_user_id(groupid,netid)
    if(userid == -1):
        return -1
    try:
        session.query(Group_members).filter_by(inc=userid).update({Group_members.grouppreferences : preferences})
        session.commit()
    except:
        session.rollback()
        print('Change_user_preferences_group() failed',file=stderr)
        return -1
    return


#used in above function to access primary key
#not intended for use in standalone function
def get_user_id(groupid,netid):
    try:
        userid = session.query(Group_members.inc).filter_by(groupid=groupid,netid=netid).first()
        # there's no inc key in users table? -> inc key is in groupmembers
        return userid
    except:
        print('get_user_id() failed',file=stderr)
        return -1

# Adds a group, shiftSchedule is optional argument if known
# should call add_user_to_group with owner role
def add_group(owner, groupName, shiftSchedule = None, globalshifts=None):
    statement = Groups(owner=owner, groupname=groupName,shiftSchedule=shiftSchedule, globalschedule=globalshifts)
    try:
        session.add(statement)
        session.flush()
        groupid=statement.groupid
        add_user_to_group(groupid,owner,'owner')
        session.commit()
        return groupid
    except:
        session.rollback()
        print('Failed to add_group()',file=stderr)
        return -1
        
# returns the global shifts for a group
def get_group_shifts(groupid):
    try:
        shift_schedule = session.query(Groups.globalschedule).filter_by(groupid=groupid).first()
        return shift_schedule[0]
    except:
        
        print("Unable to get the group shift schedule for group:",groupid, file=stderr)
        return -1



# changes the recurring shifts for a group
def change_group_shifts(groupid, shifts = None):
    try:
        session.query(Groups).filter_by(groupid=groupid).update({Groups.globalschedule : shifts})
        session.commit()
        return

    except:
        session.rollback()
        print("Failed to change group shifts",file=stderr)
        return -1


# removes a group
def remove_group(groupid):
    try:
        session.execute(
            "DELETE FROM groupmembers WHERE groupid=:param", {"param":groupid}
        )
        session.execute(
            "DELETE FROM groups WHERE groupid=:param", {"param":groupid}
        )
        # session.delete(Group_members(inc=get_user_id(groupid,netid)))
        session.flush()
        session.commit()
    except:
        session.rollback()
        print('Failed to remove group',file=stderr)
        return -1
    return

# returns the current schedule for a group
def get_group_schedule(groupid):
    try:
        schedule = session.query(Groups.shiftSchedule).filter_by(groupid=groupid).first()
        return schedule[0]
    except:
        print("Unable to get the current schedule for group:",groupid, file=stderr)
        return -1

# Replaces the schedule of the group specified by groupid
def change_group_schedule(groupid, schedule):
    try:
        session.query(Groups).filter_by(groupid=groupid).update({Groups.shiftSchedule : schedule})
        session.commit()
    except:
        session.rollback()
        print('change_group_schedule() failed',file=stderr)
        return -1
    return

# add a user (netid) to group (groupid), 
# preferences is optional argument, but could default to global if None???
# valid options for 'role' are: 'manager', 'owner', 'member'
def add_user_to_group(groupid, netid, role, email=False,text=False,preferences = None):
    try:
        session.add(Group_members(netid=netid,groupid=groupid,role=role,emailnotif=email,textnotif=text,grouppreferences=preferences))
        session.commit()
    except:
        session.rollback()
        print('Failed to add user to group',file=stderr)
        return -1
    return

# changes the role of a person (netid) in a group (groupid) to 'role'
def change_group_role(groupid, netid, role):
    userid=get_user_id(groupid,netid)
    if userid == -1:
        print('failed to change user role in group',file=stderr)
        return -1
    try:
        session.query(Group_members).filter_by(inc=userid).update({Group_members.role : role})
        session.commit()
    except:
        session.rollback()
        print('failed to change user role in group',file=stderr)
        return -1
    return

# change the notifications of a person in a group
# email and text should always be specified when calling this function
def change_group_notifications(groupid, netid, emailnotif = False, textnotif = False):
    userid = get_user_id(groupid,netid)
    if userid == -1:
        print('failed to change group notifications',file=stderr)
        return -1
    try:
        session.query(Group_members).filter_by(inc=userid).update({Group_members.emailnotif: emailnotif, Group_members.textnotif:textnotif})
        session.commit()
    except:
        session.rollback()
        print('failed to change group notifications',file=stderr)
        return -1
    return

# retrieve name, email, phone from user table
def get_profile_info(netid):
    try:
        userInfo = session.query(Users.firstname, Users.lastname, Users.email, Users.phone).filter_by(netid=netid).first()
        return userInfo
    except:
        print('Failed to get profile info',file=stderr)
        return -1

# retrieve user's notification preferences from specific group
def get_group_notifications(netid, groupid):
    try:
        userid = get_user_id(groupid, netid)
        notifPrefs = session.query(Group_members.emailnotif, Group_members.textnotif).filter_by(inc=userid).first()
        return notifPrefs
    except:
        print('Failed to get group notifications',file=stderr)
        return -1


def get_user_schedule(netid,groupid):
    userid = get_user_id(groupid,netid)
    if userid == -1:
        return -1
    try:
        sched = session.query(Group_members.userschedule).filter_by(inc=userid).first()
        return sched
    except:
        print("failed to get user schedule",file=stderr)
        return -1

def update_user_schedule(netid,groupid, schedule = None):
    userid = get_user_id(groupid,netid)
    if userid == -1:
        return -1
    try:
        session.query(Group_members).filter_by(inc=userid).update({Group_members.userschedule : schedule})
        session.commit()
        return

    except:
        session.rollback()
        print("failed to update user schedule",file=stderr)
        return -1

# updates profile info
# (name, email, phone)
def update_profile_info(firstName, lastName, netid, email=None, phone=None, preferences=None, createGroup = True):
    try:
        session.query(Users).filter_by(netid=netid).update({Users.firstname : firstName, Users.lastname: lastName, 
                            Users.email: email, Users.phone: phone,Users.can_create_group: createGroup, Users.globalpreferences: preferences})
        session.commit()
    except:
        session.rollback()
        print('Failed to update user profile',file=stderr)
        return -1
    return

# get all groupids of groups that user is part of 
# returns list of tuples, (groupid, groupname)
def get_user_groups(netid):
    try:
        groups = session.query(Group_members.groupid).filter_by(netid=netid).all()
        if len(groups) == 0:
            return groups
        group_list = []
        for g in groups:
            name = session.query(Groups.groupname).filter_by(groupid=g.groupid).first()
            group_list.append((g.groupid,name[0]))
        return group_list
    except:
        print('get user groups failed',file=stderr)
        return -1

def get_group_id(groupname):
    try:
        groupid = session.query(Groups.groupid).filter_by(groupname=groupname).first()
        return groupid.groupid
    except:
        print('failed to get groupid',file=stderr)
        return -1

# return True if user in 1+ groups, False if in none
def in_group(netid):
    try:
        ingroup = session.query(Group_members.netid).filter_by(netid=netid).first()
        return (ingroup != None)
    except:
        print('in group query failed', file=stderr)
        return -1

def get_user_role(netid, groupid):
    try:
        userid = get_user_id(groupid, netid)
        role = session.query(Group_members.role).filter_by(inc=userid).first()
        return role.role
    except:
        print('get user role failed')
        return -1

# returns a list of user netids from a group
def get_group_users(groupid):
    try:
        netids = session.query(Group_members.netid).filter_by(groupid=groupid)
        id_array = []
        for netid in netids:
            id_array.append(netid[0])
        return id_array
    except Exception as e:
        print("exception")
        print(e)
        return -1

def rollback():
    session.rollback()
    return

if __name__=="__main__":
    # test
    # add_user('batya','stein','batyas',email='batyas@princeton.edu',phone='7327660532')
    #add_user_to_group(1, 'batyas','member')

    #update_profile_info('test', 'user', 'test123', email = 'test@test.com', preferences=create_preferences([[1,2],[1,2]]))
    #print(user_exists('test2'))
    #add_group('dlsnyder', 'Test Group 2')
    #add_user_to_group(3, 'test2', 'user')
    #groups = get_user_groups('test2')
    #print(groups)
    #print(get_group_notifications('test2',1))
    #change_group_notifications(1, 'test2')
    #print(get_group_notifications('test2',1))

    #print(get_group_preferences(1,'test2'))
    '''
    print(get_group_preferences(1, 'test2'))
    change_user_preferences_group(1, 'test2')
    print(get_group_preferences(1, 'test2'))
    '''
    #print(get_user_role('batyas',28))
    #print(get_user_groups('batyas'))
    #change_group_schedule(52, {"0_1_2":["batyas","bates", "kevin"], "0_2_3":["hi1"],"1_4_5":["hi2"],"1_0_1":["hi3","b"]})
    #print(parse_user_schedule("batyas", get_group_schedule(52)))