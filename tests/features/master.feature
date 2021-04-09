Feature: SDP Master Device

    Scenario: Device is initialised in the correct state
        Given I have an SDPMaster device
        Then the state should be STANDBY
        And healthState should be OK
        And the log should not contain a transaction ID

    Scenario Outline: Command succeeds in allowed state
        Given I have an SDPMaster device
        And the state is <initial_state>
        When I call <command>
        Then the state should be <final_state>
        And the log should contain a transaction ID

        Examples:
        | command | initial_state | final_state |
        | Off     | STANDBY       | OFF         |
        | Off     | DISABLE       | OFF         |
        | Off     | ON            | OFF         |
        | Standby | OFF           | STANDBY     |
        | Standby | DISABLE       | STANDBY     |
        | Standby | ON            | STANDBY     |
        | Disable | OFF           | DISABLE     |
        | Disable | STANDBY       | DISABLE     |
        | Disable | ON            | DISABLE     |
        | On      | OFF           | ON          |
        | On      | STANDBY       | ON          |
        | On      | DISABLE       | ON          |

    Scenario Outline: Command is rejected in disallowed state
        Given I have an SDPMaster device
        And the state is <initial_state>
        Then calling <command> should raise tango.DevFailed

        Examples:
        | command | initial_state |
        | Off     | OFF           |
        | Standby | STANDBY       |
        | Disable | DISABLE       |
        | On      | ON            |
