// This file is a copy of:
// https://github.com/prep/pubsubc/blob/acd31b169239c1a8f0ed4d2a45d8a9e6f813a4a0/main.go
// All credit for this work goes to the original author.
package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"runtime"
	"strings"

	"cloud.google.com/go/pubsub"
)

var (
	debug   = flag.Bool("debug", false, "Enable debug logging")
	help    = flag.Bool("help", false, "Display usage information")
	version = flag.Bool("version", false, "Display version information")
)

// The CommitHash and Revision variables are set during building.
var (
	CommitHash = "<not set>"
	Revision   = "<not set>"
)

// Topics describes a PubSub topic and its subscriptions.
type Topics map[string][]string

func versionString() string {
	return fmt.Sprintf("pubsubc - build %s (%s) running on %s", Revision, CommitHash, runtime.Version())
}

// debugf prints debugging information.
func debugf(format string, params ...interface{}) {
	if *debug {
		fmt.Printf(format+"\n", params...)
	}
}

// fatalf prints an error to stderr and exits.
func fatalf(format string, params ...interface{}) {
	fmt.Fprintf(os.Stderr, os.Args[0]+": "+format+"\n", params...)
	os.Exit(1)
}

// create a connection to the PubSub service and create topics and subscriptions
// for the specified project ID.
func create(ctx context.Context, projectID string, topics Topics) error {
	client, err := pubsub.NewClient(ctx, projectID)
	if err != nil {
		return fmt.Errorf("Unable to create client to project %q: %s", projectID, err)
	}
	defer client.Close()

	debugf("Client connected with project ID %q", projectID)

	for topicID, subscriptions := range topics {
		debugf("  Creating topic %q", topicID)
		topic, err := client.CreateTopic(ctx, topicID)
		if err != nil {
			return fmt.Errorf("Unable to create topic %q for project %q: %s", topicID, projectID, err)
		}

		for _, subscriptionID := range subscriptions {
			debugf("    Creating subscription %q", subscriptionID)
			_, err = client.CreateSubscription(ctx, subscriptionID, pubsub.SubscriptionConfig{Topic: topic})
			if err != nil {
				return fmt.Errorf("Unable to create subscription %q on topic %q for project %q: %s", subscriptionID, topicID, projectID, err)
			}
		}
	}

	return nil
}

func main() {
	flag.Parse()
	flag.Usage = func() {
		fmt.Printf(`Usage: env PUBSUB_PROJECT1="project1,topic1,topic2:subscription1" %s`+"\n", os.Args[0])
		flag.PrintDefaults()
	}

	if *help {
		flag.Usage()
		return
	}

	if *version {
		fmt.Println(versionString())
		return
	}

	// Cycle over the numbered PUBSUB_PROJECT environment variables.
	for i := 1; ; i++ {
		// Fetch the enviroment variable. If it doesn't exist, break out.
		currentEnv := fmt.Sprintf("PUBSUB_PROJECT%d", i)
		env := os.Getenv(currentEnv)
		if env == "" {
			// If this is the first environment variable, print the usage info.
			if i == 1 {
				flag.Usage()
				os.Exit(1)
			}

			break
		}

		// Separate the projectID from the topic definitions.
		parts := strings.Split(env, ",")
		if len(parts) < 2 {
			fatalf("%s: Expected at least 1 topic to be defined", currentEnv)
		}

		// Separate the topicID from the subscription IDs.
		topics := make(Topics)
		for _, part := range parts[1:] {
			topicParts := strings.Split(part, ":")
			topics[topicParts[0]] = topicParts[1:]
		}

		// Create the project and all its topics and subscriptions.
		if err := create(context.Background(), parts[0], topics); err != nil {
			fatalf(err.Error())
		}
	}
}
