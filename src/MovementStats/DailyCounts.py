import graphlab as gl
import argparse
import csv
import sys

def update_dict(x):
    result={}
    for each in x:
            result.update(each)
    return result


def count_ab(lst, a, b):
	count=0
	if len(lst)==1 and a==b: #The user made one call 
		count=1
	elif len(lst)==1 and a!=b:
		count=0
	else:
		for i in range(1,len(lst)):
			if lst[i]==b and lst[i-1]==a:
				count+=1
	return count

'''
Counting all the entries greater than 1 as 1
'''
def binary_encode(x):
	if x==0:
		return 0
	else :
		return 1


def preprocess(inputfile, tower_town_file):
		filename=inputfile
		sf=gl.SFrame.read_csv(filename, delimiter='|', header=False)
		sf['X5']=sf['X5'].apply(lambda x:x.replace('u',''))
		sf['X6']=sf['X6'].apply(lambda x:x.replace('u',''))
		sf_Caller=sf[['X1','X2','X5']]
		sf_Callee=sf[['X1','X3','X6']]
		sf_Caller=sf_Caller.filter_by('','X5',exclude=True)
		sf_Callee=sf_Callee.filter_by('','X6',exclude=True)

		sf_Caller.rename({'X1':'DateTime','X2':'Subscriber','X5':'Tower'})
		sf_Callee.rename({'X1':'DateTime','X3':'Subscriber','X6':'Tower'})

		sf_union=sf_Caller.append(sf_Callee)

		sf_union['Subscriber']=sf_union['Subscriber'].apply(lambda x:x.split(' ')[0]) # get rid of every thing after space
		sf_union['Subscriber']=sf_union['Subscriber'].apply(lambda x:x.replace('00E','')) # get rid of OOE
		sf_union['Subscriber']=sf_union['Subscriber'].apply(lambda x:x.replace('.','')) # get rid of .


		sf_towns=gl.SFrame.read_csv(tower_town_file, header=False)
		sf_towns.rename({'X1':'Tower','X2':'TownName'})

		sf_towns['TownName']=sf_towns['TownName'].apply(lambda x:x.replace(' ','')) #replacing space

		sf_merged=sf_union.join(sf_towns, on='Tower')
		sf_merged['Date']=sf_merged['DateTime'].apply(lambda x:x.split(' ')[0])
		return sf_merged

def count_subscribers_per_town(sf_merged):
        DailyVisits=sf_merged.groupby(['Date','TownName'],operations={'Subscribers':gl.aggregate.CONCAT('Subscriber')})
        # Making sure that the graphlab treats the user ids as string while exporting the data
        DailyVisits['Subscribers']=DailyVisits['Subscribers'].apply(lambda x:list(set(x)))
        DailyVisits['Subscribers']=DailyVisits['Subscribers'].apply(lambda x:[str(each) for each in x])
        DailyVisits['SubscribersCount']=DailyVisits['Subscribers'].apply(lambda x:len(x))

        dates=list(set(DailyVisits['Date']))+['Overall']
        #dates=['Overall']
        print dates
        #sys.exit(0)
        for dt in dates:
            print 'PROGRESS:{}'.format(dt)
            exclude=False
            if dt=='Overall':
                exclude=True
                OverallVisits=sf_merged.groupby(['TownName'],operations={'Subscribers':gl.aggregate.CONCAT('Subscriber')})
                # Making sure that the graphlab treats the user ids as string while exporting the data
                OverallVisits['Subscribers']=OverallVisits['Subscribers'].apply(lambda x:list(set(x)))
                OverallVisits['Subscribers']=OverallVisits['Subscribers'].apply(lambda x:[str(each) for each in x])
                OverallVisits['SubscribersCount']=OverallVisits['Subscribers'].apply(lambda x:len(x))
                OverallVisits[['TownName','SubscribersCount']].export_csv('DailyVisits_without_subscribers_'+str(dt)+'.csv',quote_level=csv.QUOTE_NONE)
                #sys.exit(0)
            else:
                DailyVisit_x=DailyVisits.filter_by(dt,'Date', exclude=exclude)
                #DailyVisit_x.export_csv('DailyVisits_with_subscribers.csv',quote_level=csv.QUOTE_NONE)
                DailyVisit_x[['Date','TownName','SubscribersCount']].export_csv('DailyVisits_without_subscribers_'+str(dt)+'.csv',quote_level=csv.QUOTE_NONE)

		return dates


def count_transitions(sf_merged, dates):
		print 'Generating Transition Matrices'
		# Generating Movement Transition Matrices
		exclude=False
		for dt in dates:
				if dt=='Overall':
					exclude=True
				else:
					exclude=False
				visits_summary, subscribers_summary={},{}
				sf_transits=sf_merged.filter_by(dt,'Date',exclude=exclude).unstack(column=[ 'DateTime','TownName'], new_column_name='transits')#unstack creates a dictionary in the format datetime:townname
				sf_transits2=sf_transits.groupby('Subscriber',operations={'transits':gl.aggregate.CONCAT('transits')})
				sf_transits2['transits']=sf_transits2['transits'].apply(lambda x:update_dict(x))# Merging all the dictionaries into one
				sf_transits2['transits']=sf_transits2['transits'].apply(lambda x:sorted(x.items()))# Sort the entries, This works as the key for the dictionaries was the datetime
				sf_transits2['towns']=sf_transits2['transits'].apply(lambda a:[y for x,y  in a])# Picking up the town from the sorted transits
		#[['2015-10-01 11:23:44', 'DataGunjBakhshTown'], ['2015-10-01 17:54:47', 'RaviTown'], ['2015-10-01 17:54:52', 'RaviTown'], ['2015-10-01 17:54:58', 'RaviTown']]

		# List of possible towns
				st1=set(['None', 'WaghaTown', 'AzizBhattiTown', 'ShalimarTown', 'IqbalTown', 'DataGunjBakhshTown', 'Cantonment', 'NishtarTown', 'GulbergTown', 'SamanabadTown', 'RaviTown'])

				transition_lst=[]
				for x in st1:
					for y in st1:
							transition_lst+=[str(x)+'-'+str(y)]

				for trans in transition_lst:
					town1,town2=trans.split('-')
					sf_transits2[trans]=sf_transits2['towns'].apply(lambda x:count_ab(x,town1,town2)) # This is giving the visits summary, This counts all the visists from town a to town b for a user
					sf_transits2['UserTransitions']=sf_transits2[trans].apply(lambda x:binary_encode(x)) #This is giving the user level summary, if the user made more than one visit from Town a to Town b then it will count such visits as 1
					visits_summary[trans]=sf_transits2[trans].sum()# Summary is a dictionary
					subscribers_summary[trans]=sf_transits2['UserTransitions'].sum()
				with open ('SummaryTransitions_'+str(dt)+'.csv','w') as fout:
					fout.write('Transition,Count\n')
					for each in visits_summary:
						fout.write(each+','+str(visits_summary[each])+'\n')

				with open ('Subscriber_SummaryTransitions_'+str(dt)+'.csv','w') as fout:
					fout.write('Transition,Count\n')
					for each in subscribers_summary:
						fout.write(each+','+str(subscribers_summary[each])+'\n')


def dailycounter(inputfile, tower_town_file):
		sf_merged=preprocess(inputfile, tower_town_file)
		print 'Counting Subscribers per Town'
		dates=count_subscribers_per_town(sf_merged)
		print 'Generating Transition Matrices'
		count_transitions(sf_merged, dates)

if __name__=='__main__':
	parser=argparse.ArgumentParser(description='DailyVisitsGenerator')
	parser.add_argument('-if','--input_file',help='Input File', required=True)
	parser.add_argument('-tf','--tower_file',help='Tower File', required=True)
	args=parser.parse_args()
	dailycounter(args.input_file, args.tower_file)	
