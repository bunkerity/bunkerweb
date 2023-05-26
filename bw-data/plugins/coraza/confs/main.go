package main

import (
	"encoding/json"
	"io"
	"log"
	"net/http"
	"os"
	"strings"

	"github.com/corazawaf/coraza/v3"
	"github.com/corazawaf/coraza/v3/types"
)

const (
	httpStatusBlocked int    = 403
	httpStatusError   int    = 400
	httpStatusValid   int    = 200
	info              string = "[INFO]"
	warn              string = "[WARN]"
	errors            string = "[ERR]"
)

func main() {
	//Config log structure
	logger := log.New(os.Stdout, " - CORAZA - ", log.Ldate|log.Ltime)

	logger.Print(" [INFO] Starting POC")

	wafConfig := coraza.NewWAFConfig().
		WithRequestBodyAccess(coraza.NewRequestBodyConfig().WithInMemoryLimit(1000)).
		WithDirectivesFromFile("coraza.conf")

	waf, err := coraza.NewWAF(wafConfig)

	if err != nil {
		logger.Panic(err)
	}

	if err := http.ListenAndServe(":8090", http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {

		// Check the request type (conf or http)
		if r.Header.Get("Request-type") == "conf" {
			body, err := io.ReadAll(r.Body)
			if err != nil {
				w.WriteHeader(http.StatusInternalServerError)
				return
			}
			var data map[string]interface{}
			err = json.Unmarshal(body, &data)
			if err != nil {
				w.WriteHeader(http.StatusBadRequest)
				return
			}

			if data["USE_OWASP_CRS"].(string) == "yes" {

				wafConfig.
					WithDirectivesFromFile("files/coreruleset/crs-setup.conf.example").
					WithDirectivesFromFile("files/coreruleset/rules/*.conf")
				logger.Print(" [CONF] CRS conf default")
				waf, err = coraza.NewWAF(wafConfig)
				if err != nil {
					logger.Println("Failed to create new WAF instance:", err)
					w.WriteHeader(http.StatusInternalServerError)
					return
				}

			} else {
				File := strings.Split(data["USE_OWASP_CRS"].(string), " ")

				for _, str := range File {
					wafConfig.WithDirectivesFromFile(str)
				}
				waf, err = coraza.NewWAF(wafConfig)
				if err != nil {
					logger.Println("Failed to create new WAF instance:", err)
					w.WriteHeader(http.StatusInternalServerError)
					return
				}

			}

			logger.Print(" [CONF] CRS conf valid")
			return
		}
		// Instanciate a new waf

		if r.Method != http.MethodPost {
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}

		if r.Header.Get("Request-type") == "client" {
			logger.Print(" [HTTP] inspect client request")
			body, err := io.ReadAll(r.Body)
			if err != nil {
				w.WriteHeader(http.StatusInternalServerError)
				return
			}

			// Decode body
			var data map[string]interface{}
			err = json.Unmarshal(body, &data)
			if err != nil {
				w.WriteHeader(http.StatusBadRequest)
				return
			}
			id := data["X-Coraza-ID"].(string)
			logger.Printf("[INFO] inspecting request with id %s \n", id)

			tx := waf.NewTransactionWithID(id)
			defer func() {
				tx.ProcessLogging()
				tx.Close()
			}()

			w.Header().Set("X-Coraza-Id", id)

			// Inspect request
			if it, err := processRequest(tx, data); err != nil {
				w.WriteHeader(httpStatusError)
				logger.Printf("[ERR] Request error: %s", err)
				return

			} else if it != nil {
				w.WriteHeader(httpStatusBlocked)
				logger.Print("[WARN] Request blocked")

			} else {
				w.WriteHeader(httpStatusValid)
				logger.Print("[INFO] Request accepted")

			}
			// Output matched rule(s)
			rules := tx.MatchedRules()
			for _, rule := range rules {
				if rule.Message() != "" && rule.Rule().ID() != 901340 {
					logger.Printf("[WARN] Matched ruleID: %d In file %s\n", rule.Rule().ID(), rule.Rule().File())
					logger.Printf("[WARN] More info: %s\n", rule.Message())
					logger.Printf("[WARN] Matched data: %+s\n", rule.MatchedDatas())

				}

			}

		}

	})); err != nil {
		logger.Panic(err)
	}
}

func processRequest(tx types.Transaction, data map[string]interface{}) (*types.Interruption, error) {
	var (
		client string
		cport  int
	)
	client = data["X-Coraza-IP"].(string)
	cport = 0
	tx.ProcessConnection(client, cport, "", 0)
	// Do a check if value == null not done yet
	tx.ProcessURI(data["X-Coraza-URI"].(string), data["X-Coraza-MET"].(string), "HTTP/1.0") // par default since bunkerweb already do the job sinon on ajoute une var dans lua
	headersMap := data["X-Coraza-HEAD"].(map[string]interface{})
	for key, val := range headersMap {
		// Convert the value to a string if possible, otherwise skip this header
		strVal, ok := val.(string)
		if !ok {
			continue
		}
		tx.AddRequestHeader(key, strVal)
	}
	in := tx.ProcessRequestHeaders()
	if in != nil {
		return in, nil
	}
	if data["X-Coraza-BODY"] != nil {
		reader, err := tx.RequestBodyReader()
		if err != nil {
			return nil, err
		}
		data["X-Coraza-BODY"] = io.NopCloser(reader)
	}
	bo, err := tx.ProcessRequestBody()
	if err != nil {

		return nil, err
	}
	if bo != nil {

		return bo, nil
	}

	return nil, nil
}
