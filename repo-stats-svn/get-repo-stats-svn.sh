#!/bin/bash

## TODO:
    # Add count of authors
    # Read list of repos from a file
    # Handle authentication?

# List of repos to get commit counts from
# # Comment out any repos from the list to skip
declare -a repos=(
    "https://svn.apache.org/repos/asf/ace"
    "https://svn.apache.org/repos/asf/activemq"
    "https://svn.apache.org/repos/asf/airavata"
    "https://svn.apache.org/repos/asf/allura"
    "https://svn.apache.org/repos/asf/ambari"
    "https://svn.apache.org/repos/asf/ant"
    "https://svn.apache.org/repos/asf/any23"
    "https://svn.apache.org/repos/asf/apr"
    "https://svn.apache.org/repos/asf/archiva"
    "https://svn.apache.org/repos/asf/aries"
    "https://svn.apache.org/repos/asf/attic"
    "https://svn.apache.org/repos/asf/aurora"
    "https://svn.apache.org/repos/asf/avalon"
    "https://svn.apache.org/repos/asf/avro"
    "https://svn.apache.org/repos/asf/axis"
    "https://svn.apache.org/repos/asf/beam"
    "https://svn.apache.org/repos/asf/beehive"
    "https://svn.apache.org/repos/asf/bigtop"
    "https://svn.apache.org/repos/asf/bloodhound"
    "https://svn.apache.org/repos/asf/board"
    "https://svn.apache.org/repos/asf/bookkeeper"
    "https://svn.apache.org/repos/asf/brooklyn"
    "https://svn.apache.org/repos/asf/bugs"
    "https://svn.apache.org/repos/asf/buildr"
    "https://svn.apache.org/repos/asf/bval"
    "https://svn.apache.org/repos/asf/calcite"
    "https://svn.apache.org/repos/asf/camel"
    "https://svn.apache.org/repos/asf/cassandra"
    "https://svn.apache.org/repos/asf/cayenne"
    "https://svn.apache.org/repos/asf/celix"
    "https://svn.apache.org/repos/asf/chemistry"
    "https://svn.apache.org/repos/asf/chukwa"
    "https://svn.apache.org/repos/asf/clerezza"
    "https://svn.apache.org/repos/asf/click"
    "https://svn.apache.org/repos/asf/climate"
    "https://svn.apache.org/repos/asf/cloudstack"
    "https://svn.apache.org/repos/asf/cocoon"
    "https://svn.apache.org/repos/asf/comdev"
    "https://svn.apache.org/repos/asf/commons"
    "https://svn.apache.org/repos/asf/concom"
    "https://svn.apache.org/repos/asf/continuum"
    "https://svn.apache.org/repos/asf/cordova"
    "https://svn.apache.org/repos/asf/couchdb"
    "https://svn.apache.org/repos/asf/creadur"
    "https://svn.apache.org/repos/asf/crunch"
    "https://svn.apache.org/repos/asf/ctakes"
    "https://svn.apache.org/repos/asf/curator"
    "https://svn.apache.org/repos/asf/cxf"
    "https://svn.apache.org/repos/asf/datafu"
    "https://svn.apache.org/repos/asf/db"
    "https://svn.apache.org/repos/asf/deltacloud"
    "https://svn.apache.org/repos/asf/deltaspike"
    "https://svn.apache.org/repos/asf/devicemap"
    "https://svn.apache.org/repos/asf/directmemory"
    "https://svn.apache.org/repos/asf/directory"
    "https://svn.apache.org/repos/asf/drill"
    "https://svn.apache.org/repos/asf/eagle"
    "https://svn.apache.org/repos/asf/empire-db"
    "https://svn.apache.org/repos/asf/esme"
    "https://svn.apache.org/repos/asf/etch"
    "https://svn.apache.org/repos/asf/excalibur"
    "https://svn.apache.org/repos/asf/falcon"
    "https://svn.apache.org/repos/asf/felix"
    "https://svn.apache.org/repos/asf/flex"
    "https://svn.apache.org/repos/asf/flink"
    "https://svn.apache.org/repos/asf/flume"
    "https://svn.apache.org/repos/asf/forrest"
    "https://svn.apache.org/repos/asf/fundraising"
    "https://svn.apache.org/repos/asf/geode"
    "https://svn.apache.org/repos/asf/geronimo"
    "https://svn.apache.org/repos/asf/giraph"
    "https://svn.apache.org/repos/asf/gora"
    "https://svn.apache.org/repos/asf/gump"
    "https://svn.apache.org/repos/asf/hadoop"
    "https://svn.apache.org/repos/asf/hama"
    "https://svn.apache.org/repos/asf/harmony"
    "https://svn.apache.org/repos/asf/hbase"
    "https://svn.apache.org/repos/asf/helix"
    "https://svn.apache.org/repos/asf/hive"
    "https://svn.apache.org/repos/asf/hivemind"
    "https://svn.apache.org/repos/asf/httpcomponents"
    "https://svn.apache.org/repos/asf/httpd"
    "https://svn.apache.org/repos/asf/ibatis"
    "https://svn.apache.org/repos/asf/ignite"
    "https://svn.apache.org/repos/asf/infrastructure"
    "https://svn.apache.org/repos/asf/isis"
    "https://svn.apache.org/repos/asf/jackrabbit"
    "https://svn.apache.org/repos/asf/jakarta"
    "https://svn.apache.org/repos/asf/james"
    "https://svn.apache.org/repos/asf/jclouds"
    "https://svn.apache.org/repos/asf/jena"
    "https://svn.apache.org/repos/asf/jmeter"
    "https://svn.apache.org/repos/asf/johnzon"
    "https://svn.apache.org/repos/asf/jspwiki"
    "https://svn.apache.org/repos/asf/juddi"
    "https://svn.apache.org/repos/asf/kafka"
    "https://svn.apache.org/repos/asf/karaf"
    "https://svn.apache.org/repos/asf/knox"
    "https://svn.apache.org/repos/asf/kylin"
    "https://svn.apache.org/repos/asf/labs"
    "https://svn.apache.org/repos/asf/lens"
    "https://svn.apache.org/repos/asf/lenya"
    "https://svn.apache.org/repos/asf/libcloud"
    "https://svn.apache.org/repos/asf/logging"
    "https://svn.apache.org/repos/asf/lucene"
    "https://svn.apache.org/repos/asf/lucene.net"
    "https://svn.apache.org/repos/asf/lucy"
    "https://svn.apache.org/repos/asf/mahout"
    "https://svn.apache.org/repos/asf/manifoldcf"
    "https://svn.apache.org/repos/asf/marmotta"
    "https://svn.apache.org/repos/asf/maven"
    "https://svn.apache.org/repos/asf/mesos"
    "https://svn.apache.org/repos/asf/metamodel"
    "https://svn.apache.org/repos/asf/mina"
    "https://svn.apache.org/repos/asf/mrunit"
    "https://svn.apache.org/repos/asf/myfaces"
    "https://svn.apache.org/repos/asf/nifi"
    "https://svn.apache.org/repos/asf/nutch"
    "https://svn.apache.org/repos/asf/ode"
    "https://svn.apache.org/repos/asf/ofbiz"
    "https://svn.apache.org/repos/asf/olingo"
    "https://svn.apache.org/repos/asf/oltu"
    "https://svn.apache.org/repos/asf/onami"
    "https://svn.apache.org/repos/asf/oodt"
    "https://svn.apache.org/repos/asf/oozie"
    "https://svn.apache.org/repos/asf/openjpa"
    "https://svn.apache.org/repos/asf/openmeetings"
    "https://svn.apache.org/repos/asf/opennlp"
    "https://svn.apache.org/repos/asf/openoffice"
    "https://svn.apache.org/repos/asf/openwebbeans"
    "https://svn.apache.org/repos/asf/parquet"
    "https://svn.apache.org/repos/asf/pdfbox"
    "https://svn.apache.org/repos/asf/perl"
    "https://svn.apache.org/repos/asf/phoenix"
    "https://svn.apache.org/repos/asf/pig"
    "https://svn.apache.org/repos/asf/pivot"
    "https://svn.apache.org/repos/asf/planet"
    "https://svn.apache.org/repos/asf/poi"
    "https://svn.apache.org/repos/asf/portals"
    "https://svn.apache.org/repos/asf/qpid"
    "https://svn.apache.org/repos/asf/quetzalcoatl"
    "https://svn.apache.org/repos/asf/ranger"
    "https://svn.apache.org/repos/asf/rave"
    "https://svn.apache.org/repos/asf/reef"
    "https://svn.apache.org/repos/asf/river"
    "https://svn.apache.org/repos/asf/roller"
    "https://svn.apache.org/repos/asf/samza"
    "https://svn.apache.org/repos/asf/santuario"
    "https://svn.apache.org/repos/asf/sentry"
    "https://svn.apache.org/repos/asf/serf"
    "https://svn.apache.org/repos/asf/servicemix"
    "https://svn.apache.org/repos/asf/shale"
    "https://svn.apache.org/repos/asf/shindig"
    "https://svn.apache.org/repos/asf/shiro"
    "https://svn.apache.org/repos/asf/singa"
    "https://svn.apache.org/repos/asf/sis"
    "https://svn.apache.org/repos/asf/sling"
    "https://svn.apache.org/repos/asf/spamassassin"
    "https://svn.apache.org/repos/asf/spark"
    "https://svn.apache.org/repos/asf/sqoop"
    "https://svn.apache.org/repos/asf/stanbol"
    "https://svn.apache.org/repos/asf/stdcxx"
    "https://svn.apache.org/repos/asf/steve"
    "https://svn.apache.org/repos/asf/storm"
    "https://svn.apache.org/repos/asf/stratos"
    "https://svn.apache.org/repos/asf/struts"
    "https://svn.apache.org/repos/asf/subversion"
    "https://svn.apache.org/repos/asf/synapse"
    "https://svn.apache.org/repos/asf/syncope"
    "https://svn.apache.org/repos/asf/systemds"
    "https://svn.apache.org/repos/asf/tajo"
    "https://svn.apache.org/repos/asf/tapestry"
    "https://svn.apache.org/repos/asf/tcl"
    "https://svn.apache.org/repos/asf/tez"
    "https://svn.apache.org/repos/asf/thrift"
    "https://svn.apache.org/repos/asf/tika"
    "https://svn.apache.org/repos/asf/tiles"
    "https://svn.apache.org/repos/asf/tinkerpop"
    "https://svn.apache.org/repos/asf/tomcat"
    "https://svn.apache.org/repos/asf/tomee"
    "https://svn.apache.org/repos/asf/trafficserver"
    "https://svn.apache.org/repos/asf/turbine"
    "https://svn.apache.org/repos/asf/tuscany"
    "https://svn.apache.org/repos/asf/twill"
    "https://svn.apache.org/repos/asf/uima"
    "https://svn.apache.org/repos/asf/unomi"
    "https://svn.apache.org/repos/asf/usergrid"
    "https://svn.apache.org/repos/asf/vcl"
    "https://svn.apache.org/repos/asf/velocity"
    "https://svn.apache.org/repos/asf/vxquery"
    "https://svn.apache.org/repos/asf/webservices"
    "https://svn.apache.org/repos/asf/whirr"
    "https://svn.apache.org/repos/asf/wicket"
    "https://svn.apache.org/repos/asf/wink"
    "https://svn.apache.org/repos/asf/wookie"
    "https://svn.apache.org/repos/asf/xalan"
    "https://svn.apache.org/repos/asf/xerces"
    "https://svn.apache.org/repos/asf/xml"
    "https://svn.apache.org/repos/asf/xmlbeans"
    "https://svn.apache.org/repos/asf/xmlgraphics"
    "https://svn.apache.org/repos/asf/zeppelin"
    "https://svn.apache.org/repos/asf/zest"
    "https://svn.apache.org/repos/asf/zookeeper"
    "https://svn.apache.org/repos/asf/incubator"

)

# Output CSV file path/name
svn_stats_csv_file="${0##*/}.csv"

# Metadata folder
tmp_metadata_folder="./tmp-repo-metadata"
repo_name_prefix_to_remove="https://svn.apache.org/repos/asf/"

# Starting count for this execution
starting_array_index=0

# If the output CSV file already exists, then try and get the number of the last repo that was logged
if test -f "$svn_stats_csv_file"
then

    svn_stats_csv_file_total_lines=$(wc -l "$svn_stats_csv_file" | awk '{print $1}')
    # echo "$svn_stats_csv_file exists with $svn_stats_csv_file_total_lines lines"

    last_repo_number=""
    number_regex='^[0-9]+$'

    # Iterate backwards through the file until a number is found in the first item of a line
    for (( i=0; i<svn_stats_csv_file_total_lines; i++))
    do

        # Get the last nth line of the file, and grab the first CSV column from it
        last_line_text=$( tail -n "$i" "$svn_stats_csv_file" | head -n 1 )
        # echo "last_line_text is $last_line_text"

        last_repo_number=$( echo "$last_line_text" | awk -F, '{print $1}' )
        # echo "last_repo_number is $last_repo_number"

        # If we got a number, exit the loop
        if [[ $last_repo_number =~ $number_regex ]]
        then

            break

        fi

    done

    # If we got a number in the end, then use it as the starting index array for this iteration
    if [[ $last_repo_number =~ $number_regex ]]
    then

        echo "$svn_stats_csv_file has last repo number $last_repo_number"
        starting_array_index=$((last_repo_number))

    else

        echo "$svn_stats_csv_file exists but couldn't find a repo number in the first column of any line, starting from $starting_array_index"

    fi

fi

# Output the CSV header
csv_header="Index,Date,Time,Repo,Revs,Newest Rev,Oldest Rev,Revs in the Last Month,Revs in the Last Year,Download Time,Download Revs per Second"
output_string="$repo_index,$date_string,$time_string,$repo,$revisions_count,$newest_commit_date,$oldest_commit_date,$revisions_in_last_month,$revisions_in_last_year,$download_time,$download_revs_per_sec"

echo "$csv_header" >> "$svn_stats_csv_file"
echo "$csv_header"

# Loop through the list of repos above
for (( i=starting_array_index; i<${#repos[@]}; i++))
do

    # Get the repo name
    repo=${repos[$i]}

    # Output to the console to show which repo we're trying to get to the anxious operator
    date_string=$(date +%Y-%m-%d)
    time_string=$(date +%H:%M:%S)
    repo_index=$((i+1))
    output_string="$repo_index,$date_string,$time_string,$repo"
    echo "$output_string"

    # Start the timer
    download_start_time=$(date +%s)

    # Get the repo's commit log
    svn_log=$(svn log --xml "$repo")

    # Output the commit log to tmp_metadata_folder/repo_name.xml so we only need to pull it once, and can parse it offline again if needed
    repo_short_name=${repo#"$repo_name_prefix_to_remove"}
    echo "$svn_log" > "$tmp_metadata_folder/$repo_short_name.xml"

    # Calculate the time it took to get the repo's log
    download_time=$(($(date +%s) - download_start_time))

    # Extract the oldest and newest commit dates
    # The log is sorted in reverse chronological order, with the latest commit on top
    # Date format: <date>2012-10-10T15:51:44.227958Z</date>
    svn_log_date_regex="<date>([0-9-]+)[T0-9:\.Z]+<\/date>"
    revision_dates=$(echo "$svn_log" | sed -nr "s/$svn_log_date_regex/\1/p")
    revisions_count=$(echo "$revision_dates" | wc -l | tr -d '[:space:]')
    newest_commit_date=$(echo "$revision_dates" | head -n 1)
    oldest_commit_date=$(echo "$revision_dates" | tail -n 1)

    # Calculate the rate of revisions per second over the network
    download_revs_per_sec=$(echo "$revisions_count/$download_time" | bc)

    # Get the dates from 1 year ago and 30 days ago
    date_one_month_ago=$(date -v -30d +%Y-%m-%d)
    date_one_year_ago=$(date -v -365d +%Y-%m-%d)

    # Count the number of revisions with dates between 1 year ago / 30 days ago, and today's date
    revisions_in_last_month=0
    revisions_in_last_year=0

    # Loop through the list of dates
    for (( j=0; j<${#revision_dates[@]}; j++))
    do

        # If the date is greater than 1 month ago, increment the counter
        if [[ "${revision_dates[$j]}" > "$date_one_month_ago" ]]
        then
            revisions_in_last_month=$((revisions_in_last_month+1))
        fi

        # If the date is greater than 1 year ago, increment the counter
        if [[ "${revision_dates[$j]}" > "$date_one_year_ago" ]]
        then
            revisions_in_last_year=$((revisions_in_last_year+1))
        fi

    done

    # Every 20th line, print the CSV header to the console again, to keep it in view
    if (( i % 20 == 0 ))
    then
        echo "$csv_header"
    fi

    # Create output string to reduce duplication
    output_string="$repo_index,$date_string,$time_string,$repo,$revisions_count,$newest_commit_date,$oldest_commit_date,$revisions_in_last_month,$revisions_in_last_year,$download_time,$download_revs_per_sec"

    # Output to the CSV file
    echo "$output_string" >> "$svn_stats_csv_file"

    # Output to the console to show progress to the anxious operator
    echo "$output_string"

done
