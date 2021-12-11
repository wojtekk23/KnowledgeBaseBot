import logging
from typing import List, Dict, Any, Optional, Text
from typedb.api.connection.session import SessionType
from typedb.api.connection.transaction import TransactionType

from typedb.client import TypeDB

logger = logging.getLogger(__name__)


class KnowledgeBase(object):

    def get_entities(
        self,
        entity_type: Text,
        attributes: Optional[List[Dict[Text, Text]]] = None,
        limit: int = 5,
    ) -> List[Dict[Text, Any]]:

        raise NotImplementedError("Method is not implemented.")

    def get_attribute_of(
        self, entity_type: Text, key_attribute: Text, entity: Text, attribute: Text
    ) -> List[Any]:

        raise NotImplementedError("Method is not implemented.")

    def validate_entity(
        self, entity_type, entity, key_attribute, attributes
    ) -> Optional[Dict[Text, Any]]:

        raise NotImplementedError("Method is not implemented.")

    def map(self, mapping_type: Text, mapping_key: Text) -> Text:

        raise NotImplementedError("Method is not implemented.")


class GraphDatabase(KnowledgeBase):
    """
    GraphDatabase uses a grakn graph database to encode your domain knowledege. Make
    sure to have the graph database set up and the grakn server running.
    """

    def __init__(self, uri: Text = "localhost:1729", keyspace: Text = "events"):
        self.uri = uri
        self.keyspace = keyspace
        self.me = "Wojciech Kłopotek"

    def _thing_to_dict(self, thing, tx):
        """
        Converts a thing (a TypeDB thing) to a dict for easy retrieval of the thing's
        attributes.
        """
        entity = {"id": thing.get_iid(), "type": thing.get_type().get_label().name()}
        for each in thing.as_remote(tx).get_has():
            entity[each.get_type().get_label().name()] = each.get_value()
        return entity

    def _execute_entity_query(self, query: Text) -> List[Dict[Text, Any]]:
        """
        Executes a query that returns a list of entities with all their attributes.
        """
        with TypeDB.core_client(address=self.uri) as client:
            with client.session(self.keyspace, SessionType.DATA) as session:
                with session.transaction(TransactionType.READ) as tx:
                    logger.debug("Executing TypeDB Query: " + query)
                    result_iter = tx.query().match(query)
                    entities = []
                    for result in result_iter:
                        for c in result.concepts():
                            entities.append(self._thing_to_dict(c, tx))
                    return entities

    def _execute_attribute_query(self, query: Text) -> List[Any]:
        """
        Executes a query that returns the value(s) an entity has for a specific
        attribute.
        """
        with TypeDB.core_client(address=self.uri) as client:
            with client.session(self.keyspace, SessionType.DATA) as session:
                with session.transaction(TransactionType.READ) as tx:
                    print("Executing TypeDB Query: " + query)
                    result_iter = tx.query().match(query)
                    l = list(result_iter)
                    print(l)
                    concepts = l[0].concepts()
                    print(concepts)
                    return [c.get_value() for c in concepts]

    def _execute_relation_query(
        self, query: Text, relation_name: Text
    ) -> List[Dict[Text, Any]]:
        """
        Execute a query that queries for a relation. All attributes of the relation and
        all entities participating in the relation are part of the result.
        """
        with TypeDB.core_client(address=self.uri) as client:
            with client.session(self.keyspace, SessionType.DATA) as session:
                with session.transaction(TransactionType.READ) as tx:
                    print("Executing TypeDB Query: " + query)
                    result_iter = tx.query().match(query)

                    relations = []

                    for concept in list(result_iter)[0].concepts():
                        relation_entity = concept.map().get(relation_name)
                        relation = self._thing_to_dict(relation_entity, tx)

                        for (
                            role_entity,
                            entity_set,
                        ) in relation_entity.as_remote(tx).get_players_by_role_type().items():
                            role_label = role_entity.get_label().name()
                            thing = entity_set.pop()
                            relation[role_label] = self._thing_to_dict(thing, tx)

                        relations.append(relation)

                    return relations

    def _get_me_clause(self, entity_type: Text) -> Text:
        """
        Construct the me clause. Needed to only list, for example, accounts that are
        related to me.

        :param entity_type: entity type

        :return: me clause as string
        """

        clause = ""

        # do not add the me clause to a query asking for events or people as they are
        # independent of the accounts related to me
        if entity_type not in ["person", "event"]:
            clause = (
                f"$person isa person, has name '{self.me}';"
                f"$employment(employer: $employer, employee: $person) isa employment;"
            )
        return clause

    def _get_attribute_clause(
        self, attributes: Optional[List[Dict[Text, Text]]] = None
    ) -> Text:
        """
        Construct the attribute clause.

        :param attributes: attributes

        :return: attribute clause as string
        """

        clause = ""

        if attributes:
            clause = ",".join([f"has {a['key']} '{a['value']}'" for a in attributes])
            clause = ", " + clause

        return clause

    def get_attribute_of(
        self, entity_type: Text, key_attribute: Text, entity: Text, attribute: Text
    ) -> List[Any]:
        """
        Get the value of the given attribute for the provided entity.

        :param entity_type: entity type
        :param key_attribute: key attribute of entity
        :param entity: name of the entity
        :param attribute: attribute of interest

        :return: the value of the attribute
        """
        
        if attribute not in ['place']:
            return self._execute_attribute_query(
                f"""
                match 
                    ${entity_type} isa {entity_type},
                    has {key_attribute} '{entity}',
                    has {attribute} $a;
                get $a;
                """
            )
        else:
            return self._execute_attribute_query(
                f"""
                match $tp (thing: $t, pplace: $place) isa $takes_place;
                    $t isa {entity_type},
                    has {key_attribute} '{entity}';
                    $place isa place,
                    has location $l;
                get $l;
                """
            )

    def _get_transaction_entities(
        self, attributes: Optional[List[Dict[Text, Text]]] = None
    ) -> List[Dict[Text, Any]]:
        """
        Query the graph database for transactions. Restrict the transactions
        by the provided attributes, if any attributes are given.
        As transaction is a relation, query also the related account entities.

        :param attributes: list of attributes

        :return: list of transactions
        """

        attribute_clause = self._get_attribute_clause(attributes)
        me_clause = self._get_me_clause("transaction")

        return self._execute_relation_query(
            f"match "
            f"{me_clause} "
            f"$transaction(account-of-receiver: $x, account-of-creator: $account) "
            f"isa transaction{attribute_clause}; "
            f"get $transaction;",
            "transaction",
        )

    def _get_card_entities(
        self, attributes: Optional[List[Dict[Text, Text]]] = None, limit: int = 5
    ) -> List[Dict[Text, Any]]:
        """
        Query the graph database for cards. Restrict the cards
        by the provided attributes, if any attributes are given.

        :param attributes: list of attributes
        :param limit: maximum number of cards to return

        :return: list of cards
        """

        attribute_clause = self._get_attribute_clause(attributes)
        me_clause = self._get_me_clause("card")

        return self._execute_entity_query(
            f"match "
            f"{me_clause} "
            f"$represented-by(bank-account: $account, bank-card: $card) "
            f"isa represented-by;"
            f"$card isa card{attribute_clause}; "
            f"get $card;"
        )[:limit]

    def _get_account_entities(
        self, attributes: Optional[List[Dict[Text, Text]]] = None, limit: int = 5
    ) -> List[Dict[Text, Any]]:
        """
        Query the graph database for accounts. Restrict the accounts
        by the provided attributes, if any attributes are given.
        Query the related relation contract, to obtain additional information
        about the bank and the person who owns the account.

        :param attributes: list of attributes
        :param limit: maximum number of accounts to return

        :return: list of accounts
        """

        attribute_clause = self._get_attribute_clause(attributes)
        me_clause = self._get_me_clause("account")

        entities = self._execute_relation_query(
            f"""
                match 
                $account isa account{attribute_clause}; 
                {me_clause} 
                get $contract;
            """,
            "contract",
        )[:limit]

        for entity in entities:
            for k, v in entity["offer"].items():
                entity[k] = v
            entity.pop("offer")

        return entities

    def _get_event_entities(
        self, attributes: Optional[List[Dict[Text, Text]]] = None, limit: int = 5
    ) -> List[Dict[Text, Any]]:
        """
        Query the graph database for events. Restrict the events
        by the provided attributes, if any attributes are given.

        :param attributes: list of attributes
        :param limit: maximum number of events to return

        :return: list of events
        """

        attribute_clause = self._get_attribute_clause(attributes)

        entities = self._execute_entity_query(
            f"""
                match 
                $event isa event{attribute_clause}; 
                get $event;
            """
        )[:limit]

        return entities

    def _get_person_entities(
        self, attributes: Optional[List[Dict[Text, Text]]] = None, limit: int = 5
    ) -> List[Dict[Text, Any]]:
        """
        Query the graph database for people. Restrict the people
        by the provided attributes, if any attributes are given.

        :param attributes: list of attributes
        :param limit: maximum number of persons to return

        :return: list of persons
        """

        attribute_clause = self._get_attribute_clause(attributes)

        entities = self._execute_entity_query(
            f"""
                match 
                $person isa person{attribute_clause}; 
                get $person;
            """
        )[:limit]

        return entities

    def _get_university_entities(
        self, attributes: Optional[List[Dict[Text, Text]]] = None, limit: int = 5
    ) -> List[Dict[Text, Any]]:
        """
        Query the graph database for universities. Restrict the universities
        by the provided attributes, if any attributes are given.

        :param attributes: list of attributes
        :param limit: maximum number of universities to return

        :return: list of universities
        """

        attribute_clause = self._get_attribute_clause(attributes)

        entities = self._execute_entity_query(
            f"""
                match 
                $university isa university{attribute_clause}; 
                get $university;
            """
        )[:limit]

        return entities

    def get_entities(
        self,
        entity_type: Text,
        attributes: Optional[List[Dict[Text, Text]]] = None,
        limit: int = 10,
    ) -> List[Dict[Text, Any]]:
        """
        Query the graph database for entities of the given type. Restrict the entities
        by the provided attributes, if any attributes are given.

        :param entity_type: the entity type
        :param attributes: list of attributes
        :param limit: maximum number of entities to return

        :return: list of entities
        """

        # if entity_type == "transaction":
        #     return self._get_transaction_entities(attributes)
        # if entity_type == "account":
        #     return self._get_account_entities(attributes, limit)
        # if entity_type == "card":
        #     return self._get_card_entities(attributes, limit)

        if entity_type == "event":
            return self._get_event_entities(attributes, limit)
        if entity_type == "person":
            return self._get_person_entities(attributes, limit)
        if entity_type == "university":
            return self._get_university_entities(attributes, limit)

        me_clause = self._get_me_clause(entity_type)
        attribute_clause = self._get_attribute_clause(attributes)

        return self._execute_entity_query(
            f"match "
            f"{me_clause} "
            f"${entity_type} isa {entity_type}{attribute_clause}; "
            f"get ${entity_type};"
        )[:limit]

    def map(self, mapping_type: Text, mapping_key: Text) -> Text:
        """
        Query the given mapping table for the provided key.

        :param mapping_type: the name of the mapping table
        :param mapping_key: the mapping key

        :return: the mapping value
        """

        value = self._execute_attribute_query(
            f"match "
            f"$mapping isa {mapping_type}, "
            f"has mapping-key '{mapping_key}', "
            f"has mapping-value $v;"
            f"get $v;"
        )

        if value and len(value) == 1:
            return value[0]

    def validate_entity(
        self, entity_type, entity, key_attribute, attributes
    ) -> Dict[Text, Any]:
        """
        Validates if the given entity has all provided attribute values.

        :param entity_type: entity type
        :param entity: name of the entity
        :param key_attribute: key attribute of entity
        :param attributes: attributes

        :return: the found entity
        """
        attribute_clause = self._get_attribute_clause(attributes)

        value = self._execute_entity_query(
            f"match "
            f"${entity_type} isa {entity_type}{attribute_clause}, "
            f"has {key_attribute} '{entity}'; "
            f"get ${entity_type};"
        )

        if value and len(value) == 1:
            return value[0]


class InMemoryGraph(KnowledgeBase):
    """
    If you don't want to use a graph database and you just have a few data points, you
    can also store your domain knowledge, for example, in a dictionary.
    This class is an example class that uses a python dictionary to encode some domain
    knowledge about banks.
    """

    def __init__(self):
        self.graph = {
            "bank": [
                {
                    "name": "N26",
                    "headquarters": "Berlin",
                    "country": "Germany",
                    "free-accounts": "true",
                },
                {
                    "name": "bunq",
                    "headquarters": "Amsterdam",
                    "country": "Netherlands",
                    "free-accounts": "false",
                },
                {
                    "name": "Deutsche Bank",
                    "headquarters": "Frankfurt am Main",
                    "country": "Germany",
                    "free-accounts": "false",
                },
                {
                    "name": "Commerzbank",
                    "headquarters": "Frankfurt am Main",
                    "country": "Germany",
                    "free-accounts": "true",
                },
                {
                    "name": "Targobank",
                    "headquarters": "Düsseldorf",
                    "country": "Germany",
                    "free-accounts": "true",
                },
                {
                    "name": "DKB",
                    "headquarters": "Berlin",
                    "country": "Germany",
                    "free-accounts": "true",
                },
                {
                    "name": "Comdirect",
                    "headquarters": "Quickborn",
                    "country": "Germany",
                    "free-accounts": "true",
                },
            ]
        }

        self.attribute_mapping = {
            "headquarters": "headquarters",
            "HQ": "headquarters",
            "main office": "headquarters",
            "city": "headquarters",
            "name": "name",
            "country": "country",
            "free-accounts": "free-accounts",
            "free accounts": "free-accounts",
        }
        self.entity_type_mapping = {"banks": "bank", "bank": "bank"}
        self.mention_mapping = {
            "first": 0,
            "second": 1,
            "third": 2,
            "fourth": 3
        }

    def get_entities(
        self,
        entity_type: Text,
        attributes: Optional[List[Dict[Text, Text]]] = None,
        limit: int = 5,
    ) -> List[Dict[Text, Any]]:
        """
        Query the graph database for entities of the given type. Restrict the entities
        by the provided attributes, if any attributes are given.

        :param entity_type: the entity type
        :param attributes: list of attributes
        :param limit: maximum number of entities to return

        :return: list of entities
        """
        if entity_type not in self.graph:
            return []

        entities = self.graph[entity_type]

        # filter entities by attributes
        if attributes:
            entities = list(
                filter(
                    lambda e: [e[a["key"]] == a["value"] for a in attributes].count(
                        False
                    )
                    == 0,
                    entities,
                )
            )

        return entities[:limit]

    def get_attribute_of(
        self, entity_type: Text, key_attribute: Text, entity: Text, attribute: Text
    ) -> List[Any]:
        """
        Get the value of the given attribute for the provided entity.

        :param entity_type: entity type
        :param key_attribute: key attribute of entity
        :param entity: name of the entity
        :param attribute: attribute of interest

        :return: the value of the attribute
        """
        if entity_type not in self.graph:
            return []

        entities = self.graph[entity_type]

        entity_of_interest = list(
            filter(lambda e: e[key_attribute] == entity, entities)
        )

        if not entity_of_interest or len(entity_of_interest) > 1:
            return []

        return [entity_of_interest[0][attribute]]

    def validate_entity(
        self, entity_type, entity, key_attribute, attributes
    ) -> Optional[Dict[Text, Any]]:
        """
        Validates if the given entity has all provided attribute values.

        :param entity_type: entity type
        :param entity: name of the entity
        :param key_attribute: key attribute of entity
        :param attributes: attributes

        :return: the found entity
        """
        if entity_type not in self.graph:
            return None

        entities = self.graph[entity_type]

        entity_of_interest = list(
            filter(lambda e: e[key_attribute] == entity, entities)
        )

        if not entity_of_interest or len(entity_of_interest) > 1:
            return None

        entity_of_interest = entity_of_interest[0]

        for a in attributes:
            if entity_of_interest[a["key"]] != a["value"]:
                return None

        return entity_of_interest

    def map(self, mapping_type: Text, mapping_key: Text) -> Text:
        """
        Query the given mapping table for the provided key.

        :param mapping_type: the name of the mapping table
        :param mapping_key: the mapping key

        :return: the mapping value
        """

        if (
            mapping_type == "attribute-mapping"
            and mapping_key in self.attribute_mapping
        ):
            return self.attribute_mapping[mapping_key]

        if (
            mapping_type == "entity-type-mapping"
            and mapping_key in self.entity_type_mapping
        ):
            return self.entity_type_mapping[mapping_key]
        
        if (
            mapping_type == "mention-mapping"
            and mapping_key in self.mention_mapping
        ):
            return self.mention_mapping[mapping_key]
