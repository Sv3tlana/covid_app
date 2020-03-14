import dtk_nodedemog as nd
import dtk_generic_intrahost as gi
import gc
import json
import pdb
import os
import datetime
import csv

# TODO: Replace all 1.0 dt's with variable.

prevalence = []
exposeds = []
active_prevalence = []
susceptible = []
recovered = []
disdeaths = []

def setup_vd_callbacks():
    gi.set_mortality_callback( mortality_callback )
    nd.set_conceive_baby_callback( conceive_baby_callback )
    nd.set_update_preg_callback( update_pregnancy_callback )

def conceive_baby_callback( individual_id, duration ):
    print( "{0} just got pregnant".format( individual_id ) )
    gi.initiate_pregnancy( individual_id )

def update_pregnancy_callback( individual_id, dt ):
    return gi.update_pregnancy( individual_id, int(dt) )

def mortality_callback( age, sex ):
    #print( "Getting mortality rate for age {0} and sex {1}.".format( age, sex ) )
    mortality_rate = nd.get_mortality_rate( ( age, sex ) )
    return mortality_rate

def is_incubating( person ):
    if gi.is_infected( person ) and gi.get_infectiousness( person ) == 0:
        return True
    else:
        return False

fertility = None
def do_shedding_update( human_pop ):
    # This is not optimal. Only optimize if it really helps
    global fertility
    if fertility is None:
        config = json.loads( open( "nd.json" ).read() )
        fertility = config["Enable_Birth"] and config["Enable_Vital_Dynamics"]
    stat_pop = 0
    for human in human_pop:
        hum_id = human["id"]
        mcw = gi.get_mcw( hum_id )
        #Can we make this conditional on 
        if fertility:
            nd.update_node_stats( ( mcw, 0, gi.is_possible_mother(hum_id), 0 ) ) # mcw, infectiousness, is_poss_mom, is_infected
        """
        if gi.is_infected(hum_id):
            if gi.has_latent_infection(hum_id):
                print( "{0} has latent infection.".format( hum_id ) )
            else:
                print( "{0} has active infection (I guess).".format( hum_id ) )
        else:
            print( "{0} has no infection.".format( hum_id ) )
        """
        stat_pop += mcw
        if gi.is_infected( hum_id ):
            gi.update1( hum_id ) # this should do shedding & vital-dynamics
    return stat_pop

def save_output( tag ): #, susceptible, exposeds, prevalence, recovered, disdeaths ):
    filename = os.path.join(os.getcwd(), "output", tag + datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S.csv'))
    if not os.path.exists( "output" ):
        os.mkdir( "output" )
    datadict = { "S": susceptible, "E": exposeds, "I": prevalence, "R": recovered, "D": disdeaths } 
    
    # Design choice: Not imposing pandas dependency
    with open( filename, 'w' ) as datafile: 
        mywriter = csv.DictWriter( datafile,fieldnames=["S","E","I","R","D"] )
        mywriter.writeheader()
        for idx in range(len(datadict["S"])):
            mywriter.writerow( {'S': datadict['S'][idx], 'E': datadict["E"][idx], 'I': datadict["I"][idx], 'R': datadict["R"][idx], 'D': datadict["D"][idx]})


def do_vitaldynamics_update( human_pop, graveyard, contagion, census_cb = None, death_cb = None ):
    num_infected = 0
    num_incubating = 0
    num_active = 0
    num_suscept = 0
    num_recover = 0
    num_people = 0
    num_deaths = 0
    new_graveyard = []

    for human in human_pop:
        hum_id = human["id"]
        if census_cb != None:
            census_cb( hum_id )

        gi.update2( hum_id ) # this should do exposure; possible optimization would be to skip this entirely if zero contagion

        mcw = gi.get_mcw( hum_id )
        if gi.is_dead( hum_id ):
            # somebody died
            print( "{0} is dead.".format( hum_id ) )
            new_graveyard.append( human )
            num_deaths += mcw # can't use len(graveyard) coz mcw
            if death_cb != None:
                death_cb( hum_id )

        num_people += mcw
        global fertility
        if fertility:
            ipm = gi.is_possible_mother( hum_id )
            ip = gi.is_pregnant( hum_id )
            if hum_id == 0:
                pdb.set_trace()
            age = gi.get_age( hum_id )
            #print( "Calling cfp with {0}, {1}, {2}, and {3}.".format( str(ipm), str(ip), str(age), str(hum_id) ) )
            # TBD: Optimization? I happen to know that this is only necessary for females of a 
            # certain age. But technically that knowledge is for nd.
            nd.consider_for_pregnancy( ( ipm, ip, hum_id, age, 1.0 ) )

        #print( str( json.loads(gi.serialize( hum_id ))["individual"]["susceptibility"] ) )
        if gi.is_infected( hum_id ):
            if is_incubating( hum_id ):
                num_incubating += mcw
            else:
                num_infected += mcw # TBD: use_mcw
        elif gi.get_immunity( hum_id ) != 1.0:
            num_recover += mcw # TBD: use mcw
        else:
            num_suscept += mcw # TBD: use mcw
            #if gi.has_active_infection( hum_id ):
            #    num_active += 1
        # serialize seems to be broken when you had an intervention (or at least a SimpleVaccine)
        #serial_man = gi.serialize( hum_id )
        #if hum_id == 1:
            #print( json.dumps( json.loads( serial_man ), indent=4 ) )
            #print( "infectiousness: " + str( json.loads( serial_man )["individual"]["infectiousness"] ) )
    #print( "Updating fertility for this timestep." )
    for corpse in new_graveyard:
        if corpse in human_pop:
            human_pop.pop( human_pop.index( corpse ) )
        else: 
            print( "Exception trying to remove individual from python list: " + str( ex ) )
    graveyard.extend( new_graveyard )
    nd.update_fertility()
    exposeds.append( num_incubating )
    prevalence.append( num_infected )
    active_prevalence.append( num_active )
    susceptible.append( num_suscept )
    recovered.append( num_recover )
    disdeaths.append( num_deaths )
    #gc.collect()
