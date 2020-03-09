#!/usr/bin/python3

import sys
import json
import random
import pdb
import timeit

from dtk_pymod_core import *
import dtk_nodedemog as nd
import dtk_generic_intrahost as gi
#import dtk_vaccine_intervention as vi
import matplotlib.pyplot as plt

# Future report structures...
report_channels = {}
report_channels[ "Susceptible" ] = []
report_channels[ "Infected" ] = []
report_channels[ "Recovered" ] = []

"""
In this app, we want to demonstrate how fertility and mortality are configured in the DTK code.
We will start with a population of 10k (?) of uniform age. We'll let the user set the fertility 
and morality params, or walk them through the options. We will run for 1 year when they hit 'submit' 
and report back the births and/or deaths.
For births, we'll record the time of each birth and render that in a monthly bar chart on its side.
For deaths, we'll do the same, but render the age (and gender?) in a monthly bar chart.
"""

# Initialize module variables.
human_pop = []
nursery = {} # store newborn counter by timestep (dict of int to int for now)
timestep = 0
random.seed( 445 ) # I like the number 4

# constants/parameters
vaccine_disribution_timestep = 200000
outbreak_timesteps = [ 1 ]
outbreak_coverage = 0.002
#sim_duration = 55 # 180
sim_duration = 100 # 180
CHILD = 0
ADULT = 1
contagion_buckets = [0, 0]
close_schools_timestep = 54

#FROM_CHILD_TO_CHILD = 0.25
#FROM_CHILD_TO_ADULT = 0.75
#FROM_ADULT_TO_CHILD = 0.75
FROM_CHILD_TO_CHILD = 1.00
FROM_CHILD_TO_ADULT = 1.00
FROM_ADULT_TO_CHILD = 1.00
FROM_ADULT_TO_ADULT = 1.00

factors = [[FROM_CHILD_TO_CHILD, FROM_ADULT_TO_CHILD],
           [FROM_CHILD_TO_ADULT, FROM_ADULT_TO_ADULT]]

def create_person_callback( mcw, age, gender ):
    """
    This callback is required by dtk_nodedemographic during population initialization.
    It can be named anything as long as it is registered via the appropriate callback.
    It takes 3 parameters: monte-carlo weight, age, and sex.
    """
    if random.random() <= 0.23:
        age = random.randrange(0, 7300)
    else:
        age = random.randrange(7300, 36500)
    # print("Creating {}.".format("ADULT" if age >= 7300 else "CHILD"))
    # TODO: move some of this to core.
    global human_pop # make sure Python knows to use module-level variable human_pop
    #global timestep
    global nursery
    person = {}
    person["mcw"]=mcw
    person["age"]=age/365
    person["sex"]=gender

    new_id = gi.create( gender, age, mcw ) 
    person["id"]=new_id
    human_pop.append( person )
    if age == 0:
        month_step = int( timestep/30.0 )
        #print( "Made a baby on timestep {0}/month {1}.".format( str( timestep ), str( month_step ) ) )
        if month_step not in nursery:
            nursery[month_step] = ( 0, 0 )
        boys = nursery[month_step][0]
        girls = nursery[month_step][1]
        if gender == 0:
            boys += mcw
        else:
            girls += mcw 
        nursery[month_step] = ( boys, girls )

# INTERESTING TRANSMISSION CODE STARTS HERE

def expose_callback( action, prob, individual_id ):
    """
    This function is the callback for exposure. It is registered with the intrahost module
    and then called for each individual for each timestep. This is where you decide whether 
    an individual should get infected or not. In the limit, you could just return False here 
    and no-one would ever get infected. If you just returned True, everyone would be infected
    always. The expectation is that you write some code that uses the contagion shed and does
    some math. To be heterogeneous, you can use the individual id. The action and prob 
    parameters can be ignored.
    """

    # The following code is just to demo the use of TBHIV-specific getters
    if gi.is_infected( individual_id ): 
        #print( "Individual {0} is apparently already infected.".format( individual_id ) )
        return 0

    if gi.get_immunity( individual_id ) == 0:
        return 0

    global timestep
    #print( "timestep = {0}, outbreak_timestep = {1}.".format( timestep, outbreak_timestep ) )
    #if timestep in outbreak_timesteps:
    #    #if gi.get_immunity( individual_id ) == 1.0 and random.random() < 0.1: # let's infect some people at random (outbreaks)
    #    if random.random() < outbreak_coverage: # let's infect some people at random (outbreaks)
    #        print( "Let's force-infect (outbreak) uninfected, non-immune individual based on random draw." )
    #        return 1
    if (timestep == 1) and (individual_id == 13):
        return 1    # force-infect individual 13 at time 0
    else:
        if individual_id == 0:
            pdb.set_trace()

        global contagion_buckets 

        #print( "Exposing individual {0} to contagion {1}.".format( individual_id, contagion_bucket ) )

        contagion = contagion_buckets[CHILD] + contagion_buckets[ADULT]

        me = ADULT if gi.get_age(individual_id) >= 7300 else CHILD

        my_factor_from_child = factors[me][CHILD]
        my_factor_from_adult = factors[me][ADULT]

        contagion = (contagion_buckets[CHILD] * my_factor_from_child) + (contagion_buckets[ADULT] * my_factor_from_adult)
        #print( "I am an {}, exposed to contagion {}.".format( "CHILD" if me == CHILD else "ADULT", contagion ) )
        contagion /= len(human_pop)
        if gi.should_infect( ( individual_id, contagion ) ):
            return 1

    return 0

def deposit_callback( contagion, individual_id ):
    """
    This function is the callback for shedding. It is registered with the intrahost module
    and then called for each shedding individual for each timestep. This is where you collect
    contagion that you want to subsequently use for transmission. Note that the individual 
    value is only populated with non-zero values if pymod-specific SetGeneticID code is 
    turned on in the DTK. This is only example I can think of of pymod-specific code in DTK.
    """
    #print( "{0} depositing {1} contagion creates total of {2}.".format( individual, contagion, well_mixed_contagion_pool ) )
    #print( "{0} depositing {1} contagion.".format( individual, contagion ) )
    # Figure out what age bucket the individual is in.
    if individual_id == 0: # we need the DTK code to be built with the GeneticID used for the individual id. If not, this will be 0
        pdb.set_trace() 
    
    #print( "Shedding {0} into age-clan index {1}.".format( contagion, index ) )
    #age_of_infection = gi.get_infection_age( individual_id )
    #contagion = get_infectiousness( age_of_infection )
    global contagion_buckets 
    bucket_index = ADULT if gi.get_age(individual_id) >= 7300 else CHILD
    contagion_buckets[bucket_index] += contagion
    #contagion_buckets[0] += contagion

def publish_callback( human_id, event_id ):
    pass
    #print( "Broadcast event {} on {}.".format( event_id, human_id ) )

# INTERESTING TRANSMISSION CODE ENDS HERE 

def get_infectiousness( age_of_infection ):
    """
    The get_infectiousness function is an optional demo function that lets you create customized infectiousness profiles.
    The input parameter is the age of infection (for an individual) and it returns a floating point value.
    """
    # implement some simple function that changes infectiousness as a function of infection age.
    # Going with a linear ramp-up and ramp-down thing here for demo
    # you can do whatever functional form you want here. 
    inf = 0
    if age_of_infection < 30:
        inf = 0.1 * (age_of_infection)/30.
    elif age_of_infection >= 30 and age_of_infection < 60:
        inf = 0.1 * (60-age_of_infection)/30.
    #print( "inf = {0}.".format( inf ) )
    return inf;

# 
# INTERVENTION HELPERS
# 

def distribute_interventions( t ):
    """
    Function to isolated distribution of interventions to individuals.
    Interventions are separate python modules. 
    """
    if t == close_schools_timestep:
        print( "SCHOOL CLOSURE INTERVENTION" )
        FROM_CHILD_TO_CHILD = 0 # 0.25
        FROM_CHILD_TO_ADULT = 0 # 0.75
        FROM_ADULT_TO_CHILD = 0 # 0.75
        #FROM_ADULT_TO_ADULT = 0
        global factors
        factors = [[FROM_CHILD_TO_CHILD, FROM_ADULT_TO_CHILD],
                   [FROM_CHILD_TO_ADULT, FROM_ADULT_TO_ADULT]]

    if t == vaccine_disribution_timestep:
        for human in human_pop:
            hum_id = human["id"] 

            # Below is code to give out anti-tb drugs
            #individual_ptr = gi.get_individual( hum_id )
            #print( "Giving anti-tb drug to {0}.".format( hum_id ) ) 
            #tdi.distribute( individual_ptr )

            # Below is code to giveout ART via function that resets ART timers
            give_art( hum_id )

            #Below is code to give out vaccines; this should be updated to use the distribute method
            #print( "Giving simple vaccine to {0}.".format( hum_id ) )
            #vaccine = vi.get_intervention()
            #gi.give_intervention( ( hum_id, vaccine ) )

    # For trivial demo, remove ART after two years.
    elif t == vaccine_disribution_timestep+730:
        for human in human_pop:
            hum_id = human["id"] 
            remove_art( hum_id )


def setup_callbacks():
    """
    The setup_callbacks function tells the PyMod modules which functions (callbacks or delegates)
    to invoke for vital dynamics and transmission.
    """
    # set creation callback
    nd.set_callback( create_person_callback )
    # set vital dynamics callbacks
    gi.my_set_callback( expose_callback )
    gi.set_deposit_callback( deposit_callback )
    setup_vd_callbacks()

def run( from_script = False ):
    """
    This is the main function that actually runs the demo, as one might expect. It does the folllowing:
    - Register callbacks
    - Create human population
    - Foreach timestep:
        - Do shedding loop for each individual
        - Calculate adjusted force of infection
        - Do vital dynamics & exposure update for each individual
        - Distribute interventions
        - "Migration"
    - Plot simple reports summarizing results
    """
    global human_pop # make sure Python knows to use module-level variable human_pop
    del human_pop[:]

    setup_callbacks()
    nd.populate_from_files() 
    if len(human_pop) == 0:
        print( "Failed to create any people in populate_from_files. This isn't going to work!" )
        sys.exit(0)

    graveyard = []
    global timestep
    global contagion_buckets 
    for t in range(0,sim_duration): # for one year
        timestep = t

        do_shedding_update( human_pop )
        # contagion_bucket /= len(human_pop)
        do_vitaldynamics_update( human_pop, graveyard ) 
        distribute_interventions( t )

        #report_channels[ "Infected" ].append( prevalence[-1] )
        print( "At end of timestep {0} num_infected = {1} stat_pop = {2}, disease deaths = {3}.".format( t, prevalence[-1], len(human_pop), len(graveyard) ) )
        contagion_buckets = [0, 0]

    # Sim done: Report.
    plt.plot( susceptible, color='green', label='S' )
    plt.plot( exposeds, color='purple', label='E' )
    plt.plot( prevalence, color='orange', label='I' )
    plt.plot( recovered, color='blue', label='R' )
    plt.plot( disdeaths, color='red', label='D' )
    #plt.title( "Infections" )
    #plt.plot( report_channels[ "Infected" ], color='orange' )
    plt.xlabel( "time" )
    #plt.ylabel( "infected individuals" )
    plt.legend()
    plt.show()

    if from_script:
        print( "NURSERY\n" + json.dumps( nursery, indent=4 ) )
        print( "GRAVEYARD\n" + json.dumps( graveyard, indent=4  ) )
    return graveyard

def perf_bench():
    sillypop = []
    for _ in range(1000):
        sillypop.append( gi.create( ( 1, 1.0, 1.0 ) ) )
    start_time = timeit.default_timer()
    for t in range(7300):
        for human in sillypop:
            gi.update( human )
    elapsed = timeit.default_timer() - start_time
    print( str( elapsed ) )
    #for human in sillypop:
    #    print( gi.get_age( human ) )

if __name__ == "__main__": 
    #test_cart_prod()
    run()
    #perf_bench()
